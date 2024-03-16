from discord.ext import commands
from fuzzywuzzy import process
from bot import RainbowBot
from rainbow import RainbowData, RainbowMatch

class OngoingMatch(commands.Cog, name='Ongoing Match'):
    """Commands to interact with an ongoing match, such as banning operators or playing rounds."""
    def __init__(self, bot):
        self.bot: RainbowBot = bot

    @commands.command(name='ban')
    async def _ban(self, ctx: commands.Context, *operators):
        """Bans operators from the match. Use **!ban op1 op2...** to ban the mentioned operators from the match. You can ban as many operators as you like."""
        await self._banUnban(ctx, *operators, ban=True)

    @commands.command(name='unban')
    async def _unban(self, ctx: commands.Context, *operators):
        """Unbans operators from the match. Use **!unban op1 op2...** to unban the mentioned operators from the match."""
        await self._banUnban(ctx, *operators, ban=False)

    @commands.command(aliases=['setMap', 'map'])
    async def _setMap(self, ctx: commands.Context, *mapName):
        """Sets the map for the match. This will influence the sites displayed for defensive rounds. Use **!setMap map** to set the map. A map can be set at any point in the match. Matches without a map set will not be included in statistics."""
        match, discordMessage, canContinue = await self.bot.getMatchData(ctx)
        if not canContinue:
            return
        if ctx.message.id != discordMessage['matchMessageId'] or not discordMessage['matchMessageId']:
            await ctx.message.delete()

        if len(mapName) == 0:
            discordMessage['messageContent']['actionPrompt'] = 'You must specify a map. Use "**!setMap map**" to try again.'
            await self.bot.sendMatchMessage(ctx, discordMessage)
            return

        discordMessage['messageContent']['actionPrompt'] = ''
        mapName = ' '.join(mapName)
        couldSetMap = match.setMap(mapName)
        if couldSetMap:
            discordMessage['messageContent']['playersBanner'] = f"Playing a match with {match.playersString}{' on **' + match.map + '**' if match.map else ''}.\n"
        else:
            discordMessage['messageContent']['actionPrompt'] += f'**{mapName}** is not a valid map. Use "**!setMap map**" to try again.\n'

        if match.currRound == 0:
            if not match.bannedOperators:
                discordMessage['messageContent']['actionPrompt'] += 'Use "**!ban op1 op2...**", then "**!attack**" ⚔️ or "**!defense**" 🛡️ to start the match.'
            else:
                discordMessage['messageContent']['actionPrompt'] += 'Use "**!attack**" ⚔️ or "**!defense**" 🛡️ to start the match.'
        else:
            discordMessage['messageContent']['actionPrompt'] += 'Use "**!won**" 🇼 or "**!lost**" 🇱 to continue.'

        self.bot.saveOngoingMatch(ctx, match)
        await self.bot.sendMatchMessage(ctx, discordMessage)

    @commands.command(aliases=['attack', 'startAttack'])
    async def _startAttack(self, ctx: commands.Context):
        """Starts the match on attack."""
        await self._playMatch(ctx, 'attack')

    @commands.command(aliases=['defense', 'startDefense', 'defend'])
    async def _startDefense(self, ctx: commands.Context):
        """Starts the match on defense."""
        await self._playMatch(ctx, 'defense')

    @commands.command(aliases=['won', 'w'])
    async def _won(self, ctx: commands.Context, overtimeSide=None):
        """Marks the current round as won and starts a new round. If winning starts overtime, you must specify the side you start overtime on with **!won attack** ⚔️ or **!won defense** 🛡️."""
        match, discordMessage, canContinue = await self.bot.getMatchData(ctx)
        if not canContinue:
            return
        if ctx.message.id != discordMessage['matchMessageId'] or not discordMessage['matchMessageId']:
            await ctx.message.delete()

        if not match.playingOnSide:
            discordMessage['messageContent']['actionPrompt'] = 'You must specify what side you start on. Use **!attack** ⚔️ or **!defense** 🛡️.'
            await self.bot.sendMatchMessage(ctx, discordMessage)
            return

        if (match.currRound == 6 and match.scores["red"] == 3):
            if not overtimeSide or overtimeSide not in ['attack', 'defense']:
                discordMessage['messageContent']['actionPrompt'] = 'You must specify what side you start overtime on. Use **!won attack** ⚔️ or **!won defense** 🛡️.'
                await self.bot.sendMatchMessage(ctx, discordMessage)
                return

        if match.resolveRound('won', overtimeSide):
            self.bot.saveOngoingMatch(ctx, match)
            self.bot.saveDiscordMessage(ctx, discordMessage)
            await self._playRound(ctx)
        else:
            self.bot.saveOngoingMatch(ctx, match)
            self.bot.saveDiscordMessage(ctx, discordMessage)
            await self._endMatch(ctx)

    @commands.command(aliases=['lost', 'l'])
    async def _lost(self, ctx: commands.Context, overtimeSide=None):
        """Marks the current round as lost and starts a new round. If losing starts overtime, you must specify the side you start overtime on with **!lost attack** ⚔️ or **!lost defense** 🛡️."""
        match, discordMessage, canContinue = await self.bot.getMatchData(ctx)
        if not canContinue:
            return
        if ctx.message.id != discordMessage['matchMessageId'] or not discordMessage['matchMessageId']:
            await ctx.message.delete()

        if not match.playingOnSide:
            discordMessage['messageContent']['actionPrompt'] = 'You must specify what side you start on. Use **!attack** ⚔️ or **!defense** 🛡️.'
            await self.bot.sendMatchMessage(ctx, discordMessage)
            return

        if (match.currRound == 6 and match.scores["blue"] == 3):
            if not overtimeSide or overtimeSide not in ['attack', 'defense']:
                discordMessage['messageContent']['actionPrompt'] = 'You must specify what side you start overtime on. Use **!lost attack** ⚔️ or **!lost defense** 🛡️.'
                await self.bot.sendMatchMessage(ctx, discordMessage)
                return

        if match.resolveRound('lost', overtimeSide):
            self.bot.saveOngoingMatch(ctx, match)
            self.bot.saveDiscordMessage(ctx, discordMessage)
            await self._playRound(ctx)
        else:
            self.bot.saveOngoingMatch(ctx, match)
            self.bot.saveDiscordMessage(ctx, discordMessage)
            await self._endMatch(ctx)

    @commands.command(aliases=['swap', 'switch'])
    async def _swap(self, ctx: commands.Context, player, operator = None):
        """Swaps the operator a player is playing for another. Use **!swap operator** to swap the operator you are playing, or **!swap @player operator** to swap the operator another player is playing."""
        match, discordMessage, canContinue = await self.bot.getMatchData(ctx)
        if not canContinue:
            return
        if ctx.message.id != discordMessage['matchMessageId'] or not discordMessage['matchMessageId']:
            await ctx.message.delete()

        if match.currRound == 0:
            discordMessage['messageContent']['actionPrompt'] = 'You can only swap operators during an ongoing round. Use **!attack** ⚔️ or **!defense** 🛡️ to start the match.'
            await self.bot.sendMatchMessage(ctx, discordMessage)
            return
        
        validOperators = RainbowData.attackers if match.playingOnSide == 'attack' else RainbowData.defenders

        # No arguments given
        if player is None:
            discordMessage['messageContent']['statsBanner'] = 'You must include the operator you are swapping to. Use **!swap operator** to try again. Use **!swap @player operator** to swap another player\'s operator.'
        # Only one argument given, it has to be an operator
        if operator is None:
            operator = player
            player = ctx.author
            if not isinstance(operator, str):
                discordMessage['messageContent']['statsBanner'] = f'**{operator}** is not a valid operator. Use **!swap operator** to try again. Use **!swap @player operator** to swap another player\'s operator.'
                await self.bot.sendMatchMessage(ctx, discordMessage)
                return
        else:
            player = await commands.MemberConverter().convert(ctx, player)

        operatorMatch, score = process.extractOne(operator, validOperators)
        if score >= 75:
            operator = operatorMatch
        else:
            discordMessage['messageContent']['statsBanner'] = f'**{operator}** is not a valid operator. Use **!swap @player operator** to try again.'
            await self.bot.sendMatchMessage(ctx, discordMessage)
            return

        playerOperators, backupOperators = match.swapOperator(player, operator)

        discordMessage = self._setRoundLineup(discordMessage, match, playerOperators, backupOperators)

        self.bot.saveOngoingMatch(ctx, match)
        await self.bot.sendMatchMessage(ctx, discordMessage)

    async def _banUnban(self, ctx: commands.Context, *operators, ban=True):
        match, discordMessage, canContinue = await self.bot.getMatchData(ctx)
        if not canContinue:
            return
        if ctx.message.id != discordMessage['matchMessageId'] or not discordMessage['matchMessageId']:
            await ctx.message.delete()

        bans = ' '.join(operators)
        sanitizedBans = match.banOperators(bans, ban)

        if match.bannedOperators == []:
            discordMessage['messageContent']['banMetadata'] = 'No operators are banned in this match.\n'
        else:
            discordMessage['messageContent']['banMetadata'] = f'The following operators are banned in this match:\n{", ".join([f"**{op}**" for op in match.bannedOperators])}\n'
            unrecognizedBans = [ban for ban in zip(sanitizedBans, operators) if ban[0] is None]
            if len(unrecognizedBans) > 0:
                if ban:
                    discordMessage['messageContent']['banMetadata'] += f'The following operators were not recognized:\n{", ".join([f"**{ban[1]}**" for ban in unrecognizedBans])}\n'
                else:
                    discordMessage['messageContent']['banMetadata'] += f'The following operators were not recognized, or not banned:\n{", ".join([f"**{ban[1]}**" for ban in unrecognizedBans])}\n'

        if match.currRound == 0:
            discordMessage['messageContent']['actionPrompt'] = ''
            if not match.map:
                discordMessage['messageContent']['actionPrompt'] += 'Next, use "**!setMap map**" to set the map.\n'
            discordMessage['messageContent']['actionPrompt'] += 'You can also "**!ban**" or "**!unban**" more operators.\n'
            discordMessage['messageContent']['actionPrompt'] += 'Use "**!attack**" ⚔️ or "**!defense**" 🛡️ to start the match.'
        else:
            discordMessage['messageContent']['actionPrompt'] = 'Use "**!won**" 🇼 or "**!lost**" 🇱 to continue.'

        self.bot.saveOngoingMatch(ctx, match)
        await self.bot.sendMatchMessage(ctx, discordMessage)

    async def _playMatch(self, ctx: commands.Context, side):
        match, discordMessage, canContinue = await self.bot.getMatchData(ctx)
        if not canContinue:
            return
        if ctx.message.id != discordMessage['matchMessageId'] or not discordMessage['matchMessageId']:
            await ctx.message.delete()

        if match == None:
            discordMessage['messageContent']['playersBanner'] = 'No match in progress. Use "**!startMatch @player1 @player2...**" to start a new match.'
            await self.bot.sendMatchMessage(ctx, discordMessage, True)
            return
        
        discordMessage['messageContent']['playersBanner'] = f"Playing a match with {match.playersString}{' on **' + match.map + '**' if match.map else ''}.\n"
        
        if side == 'attack':
            match.playingOnSide = 'attack'
        else:
            match.playingOnSide = 'defense'

        if match.currRound == 0:
                match.currRound = 1

        self.bot.saveOngoingMatch(ctx, match)
        self.bot.saveDiscordMessage(ctx, discordMessage)
        await self._playRound(ctx)

    async def _playRound(self, ctx: commands.Context):
        match, discordMessage, canContinue = await self.bot.getMatchData(ctx)
        if not canContinue:
            return

        discordMessage['messageContent']['playersBanner'] = f"Playing a match with {match.playersString}{' on **' + match.map + '**' if match.map else ''}.\n"
        discordMessage['messageContent']['matchScore'] = f'The score is **{match.scores["blue"]}**:**{match.scores["red"]}**, we are playing on **{match.playingOnSide}**.\n'
        discordMessage['messageContent']['banMetadata'] = ''
        discordMessage['messageContent']['statsBanner'] = ''
        discordMessage['messageContent']['roundMetadata'] = f'Here is your lineup for round {match.currRound}:'

        operators, site = match.setupRound()
        if match.playingOnSide == 'defense':
            discordMessage['messageContent']['roundMetadata'] += f'\nChoose the **{site}** site.'

        discordMessage['messageContent']['actionPrompt'] = ''
        discordMessage['reactions'] = []

        if match.currRound != 6:
            discordMessage['messageContent']['actionPrompt'] += 'Use "**!won**" 🇼 or "**!lost**" 🇱 to continue.'
            discordMessage['reactions'] += ['🇼', '🇱']
        elif match.scores["red"] == 3:
            discordMessage['messageContent']['actionPrompt'] += 'If you won, use "**!won attack**" ⚔️ (or "**!won defense**" 🛡️) to start overtime on the specified side, otherwise use **!lost** 🇱 to end the match.'
            discordMessage['reactions'] += ['⚔️', '🛡️', '🇱']
        elif match.scores["blue"] == 3:
            discordMessage['messageContent']['actionPrompt'] += 'If you lost, use "**!lost attack**" ⚔️ (or "**!lost defense**" 🛡️) to start overtime on the specified side, otherwise use **!won** 🇼 to end the match.'
            discordMessage['reactions'] += ['🇼', '⚔️', '🛡️']

        discordMessage = self._setRoundLineup(discordMessage, match, operators)

        self.bot.saveOngoingMatch(ctx, match)
        await self.bot.sendMatchMessage(ctx, discordMessage)

    async def _endMatch(self, ctx: commands.Context):
        match, discordMessage, canContinue = await self.bot.getMatchData(ctx)
        if not canContinue:
            return

        discordMessage['messageContent']['roundMetadata'] = ''
        discordMessage['messageContent']['roundLineup'] = ''
        discordMessage['messageContent']['playersBanner'] = f"Finished a match with {match.playersString}{' on **' + match.map + '**' if match.map else ''}.\n"
        discordMessage['messageContent']['matchScore'] = f'The match is over! The final score was **{match.scores["blue"]}**:**{match.scores["red"]}**.\n'
        discordMessage['messageContent']['statsBanner'] = ''
        discordMessage['messageContent']['actionPrompt'] = 'Use "**!another**" 👍 for a new match with the same players, "**!another here**" 🎤 for a new match in your voice channel, or "**!goodnight (delete)**" 👎 (✋) to end the match (and exclude it from statistics).'
        discordMessage['reactions'] = ['👍', '🎤', '👎', '✋']
        self.bot.saveOngoingMatch(ctx, match)
        self.bot.saveCompletedMatch(ctx, match)
        await self.bot.sendMatchMessage(ctx, discordMessage)
    
    def _setRoundLineup(self, discordMessage, match: RainbowMatch, operators: list, backupOperators: list = None):
        operatorsCopy = operators.copy()

        discordMessage['messageContent']['roundLineup'] = ''
        for player, operator in zip(match.players, operatorsCopy):
            discordMessage['messageContent']['roundLineup'] += f'{player["mention"]} plays **{operator}**\n'
            operators.remove(operator)

        if backupOperators is None:
            backupOperators = operators

        if len(backupOperators) > 0:
            discordMessage['messageContent']['roundLineup'] += f'Backup operators: **{", ".join(backupOperators)}**. Use **!swap** to switch operator.\n'

        # If one of the operators is Caveira, add the interrogation emoji to the message
        if 'Caveira' in operatorsCopy and '🗡️' not in discordMessage['reactions']:
            discordMessage['reactions'] += ['🗡️']
        
        return discordMessage

async def setup(bot: RainbowBot):
    await bot.add_cog(OngoingMatch(bot))
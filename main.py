import discord
from discord.ext import commands
from discord import app_commands
import os
import random
import asyncio
import json
from datetime import datetime
from keep_alive import keep_alive

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

class Tournament:
    def __init__(self):
        self.players = []
        self.max_players = 0
        self.active = False
        self.channel = None
        self.target_channel = None
        self.message = None
        self.rounds = []
        self.results = []
        self.eliminated = []
        self.fake_count = 1
        self.map = ""
        self.abilities = ""
        self.prize_1st = ""
        self.prize_2nd = ""
        self.prize_3rd = ""
        self.prize_4th = ""
        self.title = ""
        self.mode = "1v1"
        self.match_winners = {}

def get_tournament(guild_id):
    if guild_id not in tournaments:
        tournaments[guild_id] = Tournament()
    return tournaments[guild_id]

tournaments = {}
role_permissions = {}
teams = {}
team_invitations = {}
player_teams = {}
log_channels = {}
bracket_roles = {}
host_registrations = {
    'active': False,
    'max_hosters': 0,
    'hosters': [],
    'channel': None,
    'message': None
}

def load_data():
    global role_permissions, log_channels, bracket_roles
    try:
        with open('user_data.json', 'r') as f:
            data = json.load(f)
            role_permissions = data.get('role_permissions', {})
            log_channels = data.get('log_channels', {})
            bracket_roles = data.get('bracket_roles', {})
    except FileNotFoundError:
        pass

def save_data():
    data = {
        'role_permissions': role_permissions,
        'log_channels': log_channels,
        'bracket_roles': bracket_roles
    }
    with open('user_data.json', 'w') as f:
        json.dump(data, f)

def has_permission(user, guild_id, permission_type):
    guild_str = str(guild_id)
    if guild_str not in role_permissions:
        return False
    
    if 'adr' in role_permissions[guild_str]:
        user_role_ids = [role.id for role in user.roles]
        adr_role_ids = role_permissions[guild_str]['adr']
        if any(role_id in adr_role_ids for role_id in user_role_ids):
            return True
    
    if permission_type not in role_permissions[guild_str]:
        return False
    
    user_role_ids = [role.id for role in user.roles]
    allowed_role_ids = role_permissions[guild_str][permission_type]
    
    return any(role_id in allowed_role_ids for role_id in user_role_ids)

def get_team_id(guild_id, user_id):
    guild_str = str(guild_id)
    user_str = str(user_id)
    return player_teams.get(guild_str, {}).get(user_str)

def get_team_members(guild_id, team_id):
    guild_str = str(guild_id)
    return teams.get(guild_str, {}).get(team_id, [])

def get_teammate(guild_id, user_id):
    team_id = get_team_id(guild_id, user_id)
    if not team_id:
        return None
    team_members = get_team_members(guild_id, team_id)
    for member in team_members:
        if member.id != user_id:
            return member
    return None

def create_team(guild_id, player1, player2):
    guild_str = str(guild_id)
    
    if guild_str not in teams:
        teams[guild_str] = {}
        player_teams[guild_str] = {}
    
    team_id = f"team_{len(teams[guild_str]) + 1}_{guild_id}"
    
    teams[guild_str][team_id] = [player1, player2]
    player_teams[guild_str][str(player1.id)] = team_id
    player_teams[guild_str][str(player2.id)] = team_id
    
    return team_id

def remove_team(guild_id, team_id):
    guild_str = str(guild_id)
    
    if guild_str in teams and team_id in teams[guild_str]:
        for player in teams[guild_str][team_id]:
            if str(player.id) in player_teams[guild_str]:
                del player_teams[guild_str][str(player.id)]
        
        del teams[guild_str][team_id]

def get_team_display_name(guild_id, team_members):
    if len(team_members) == 2:
        name1 = get_player_display_name(team_members[0], guild_id)
        name2 = get_player_display_name(team_members[1], guild_id)
        return f"{name1} & {name2}"
    return "Unknown Team"

def get_player_display_name(player, guild_id=None):
    if isinstance(player, FakePlayer):
        return "None"
    
    return player.name if hasattr(player, 'name') else str(player)

async def log_command(guild_id, user, command, details=""):
    guild_str = str(guild_id)
    if guild_str not in log_channels:
        return
    
    try:
        channel = bot.get_channel(log_channels[guild_str])
        if not channel:
            return
        
        embed = discord.Embed(
            title="📋 Tournament Command Used",
            color=0x3498db,
            timestamp=datetime.now()
        )
        
        embed.add_field(name="User", value=user.name, inline=True)
        embed.add_field(name="Command", value=command, inline=True)
        if details:
            embed.add_field(name="Details", value=details, inline=False)
        
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Error logging command: {e}")

async def auto_update_alllogs(guild):
    guild_str = str(guild.id)
    if guild_str not in log_channels:
        return
    
    try:
        channel = bot.get_channel(log_channels[guild_str])
        if not channel:
            return
        
        async for message in channel.history(limit=50):
            if message.author == bot.user and message.embeds:
                embed = message.embeds[0]
                if embed.title and "Bracket Roles" in embed.title:
                    new_embed = discord.Embed(
                        title="<:bracketrole:1413196441564315810> Bracket Roles",
                        color=0x9b59b6
                    )
                    
                    if guild_str in bracket_roles and bracket_roles[guild_str]:
                        roles_text = ""
                        for user_id, emojis in bracket_roles[guild_str].items():
                            try:
                                member = guild.get_member(int(user_id))
                                if member:
                                    emojis_str = ''.join(emojis)
                                    roles_text += f"{member.mention}: {emojis_str}\n"
                            except:
                                pass
                        
                        if roles_text:
                            new_embed.description = roles_text
                        else:
                            new_embed.description = "No bracket roles assigned yet."
                    else:
                        new_embed.description = "No bracket roles assigned yet."
                    
                    await message.edit(embed=new_embed)
                    return
    except Exception as e:
        print(f"Error updating alllogs: {e}")

class FakePlayer:
    def __init__(self, name, user_id):
        self.display_name = name
        self.id = user_id
        self.name = name
        self.nick = None

class InviteView(discord.ui.View):
    def __init__(self, inviter, inviter_guild_id):
        super().__init__(timeout=300)
        self.inviter = inviter
        self.inviter_guild_id = inviter_guild_id
    
    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, emoji="<:check:1400922446365855854>", custom_id="invite_accept")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_str = str(self.inviter_guild_id)
        inviter_str = str(self.inviter.id)
        invitee_str = str(interaction.user.id)
        
        inviter_team_id = get_team_id(self.inviter_guild_id, self.inviter.id)
        if inviter_team_id:
            await interaction.response.send_message("❌ The inviter is already in a team.")
            return
        
        invitee_team_id = get_team_id(self.inviter_guild_id, interaction.user.id)
        if invitee_team_id:
            await interaction.response.send_message("❌ You are already in a team.")
            return
        
        team_id = create_team(self.inviter_guild_id, self.inviter, interaction.user)
        
        if guild_str in team_invitations and invitee_str in team_invitations[guild_str]:
            if self.inviter.id in team_invitations[guild_str][invitee_str]:
                team_invitations[guild_str][invitee_str].remove(self.inviter.id)
        
        await interaction.response.send_message(f"✅ You accepted the invitation! Team created: {self.inviter.name} & {interaction.user.name}!")
        
        try:
            guild = bot.get_guild(self.inviter_guild_id)
            if guild:
                channel = guild.system_channel or guild.text_channels[0] if guild.text_channels else None
                if channel:
                    await channel.send(f"✅ Team created: {self.inviter.name} & {interaction.user.name}!")
        except:
            pass
    
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, emoji="<:uncheck:1400922538644603011>", custom_id="invite_decline")
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_str = str(self.inviter_guild_id)
        invitee_str = str(interaction.user.id)
        
        if guild_str in team_invitations and invitee_str in team_invitations[guild_str]:
            if self.inviter.id in team_invitations[guild_str][invitee_str]:
                team_invitations[guild_str][invitee_str].remove(self.inviter.id)
        
        await interaction.response.send_message(f"❌ You declined the invitation from {self.inviter.name}.")

class WinnersView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id
    
    @discord.ui.button(label="Winners", style=discord.ButtonStyle.primary, custom_id="show_winners", emoji="<:Crown:1400924187325104258>")
    async def show_winners(self, interaction: discord.Interaction, button: discord.ui.Button):
        tournament = get_tournament(self.guild_id)
        
        if not tournament.active:
            await interaction.response.send_message("❌ No active tournament.", ephemeral=True)
            return
        
        current_round = tournament.rounds[-1] if tournament.rounds else []
        round_number = len(tournament.rounds)
        
        winners_text = f"**Round {round_number} Winners:**\n\n"
        
        for i, match in enumerate(current_round, 1):
            match_key = f"round_{round_number}_match_{i}"
            
            if match_key in tournament.match_winners:
                winner = tournament.match_winners[match_key]
                if tournament.mode == "2v2":
                    winner_display = get_team_display_name(self.guild_id, winner)
                else:
                    winner_display = get_player_display_name(winner, self.guild_id)
                winners_text += f"Match {i}: **{winner_display}**\n"
            else:
                winners_text += f"Match {i}: **?**\n"
        
        await interaction.response.send_message(winners_text, ephemeral=True)

@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")
    load_data()
    
    bot.add_view(TournamentView())
    bot.add_view(HosterRegistrationView())
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    
    print("🔧 Bot is ready and all systems operational!")

class TournamentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True
    
    @discord.ui.button(label="Register", style=discord.ButtonStyle.green, custom_id="tournament_register", emoji="<:check:1400922446365855854>")
    async def register_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            tournament = get_tournament(interaction.guild.id)
            
            if tournament.max_players == 0:
                return await interaction.response.send_message("❌ No tournament has been created yet.", ephemeral=True)
            if tournament.active:
                return await interaction.response.send_message("⚠️ Tournament already started.", ephemeral=True)
            
            if tournament.mode == "2v2":
                team_id = get_team_id(interaction.guild.id, interaction.user.id)
                if not team_id:
                    return await interaction.response.send_message("❌ You need to be in a team to register for 2v2 tournaments! Use `!invite @teammate` to create a team.", ephemeral=True)
                
                team_members = get_team_members(interaction.guild.id, team_id)
                if any(member in tournament.players for member in team_members):
                    return await interaction.response.send_message("❌ Your team is already registered.", ephemeral=True)
                
                current_teams = len(tournament.players) // 2
                if current_teams >= tournament.max_players:
                    return await interaction.response.send_message("❌ Tournament is full.", ephemeral=True)
                
                tournament.players.extend(team_members)
                
                await self.update_tournament_embed(interaction, tournament)
                await interaction.response.send_message(f"✅ Team registered! ({len(tournament.players) // 2}/{tournament.max_players} teams)", ephemeral=True)
            
            else:
                if interaction.user in tournament.players:
                    return await interaction.response.send_message("❌ You are already registered.", ephemeral=True)
                
                if len(tournament.players) >= tournament.max_players:
                    return await interaction.response.send_message("❌ Tournament is full.", ephemeral=True)
                
                tournament.players.append(interaction.user)
                
                await self.update_tournament_embed(interaction, tournament)
                await interaction.response.send_message(f"✅ Registered! ({len(tournament.players)}/{tournament.max_players})", ephemeral=True)
        
        except Exception as e:
            print(f"Error in register_button: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred.", ephemeral=True)
    
    @discord.ui.button(label="Unregister", style=discord.ButtonStyle.red, custom_id="tournament_unregister", emoji="<:uncheck:1400922538644603011>")
    async def unregister_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            tournament = get_tournament(interaction.guild.id)
            
            if tournament.max_players == 0:
                return await interaction.response.send_message("❌ No tournament has been created yet.", ephemeral=True)
            if tournament.active:
                return await interaction.response.send_message("⚠️ Tournament already started.", ephemeral=True)
            
            if tournament.mode == "2v2":
                team_id = get_team_id(interaction.guild.id, interaction.user.id)
                if not team_id:
                    return await interaction.response.send_message("❌ You are not in a team.", ephemeral=True)
                
                team_members = get_team_members(interaction.guild.id, team_id)
                if not any(member in tournament.players for member in team_members):
                    return await interaction.response.send_message("❌ Your team is not registered.", ephemeral=True)
                
                for member in team_members:
                    if member in tournament.players:
                        tournament.players.remove(member)
                
                await self.update_tournament_embed(interaction, tournament)
                await interaction.response.send_message(f"✅ Team unregistered! ({len(tournament.players) // 2}/{tournament.max_players} teams)", ephemeral=True)
            
            else:
                if interaction.user not in tournament.players:
                    return await interaction.response.send_message("❌ You are not registered.", ephemeral=True)
                
                tournament.players.remove(interaction.user)
                
                await self.update_tournament_embed(interaction, tournament)
                await interaction.response.send_message(f"✅ Unregistered! ({len(tournament.players)}/{tournament.max_players})", ephemeral=True)
        
        except Exception as e:
            print(f"Error in unregister_button: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ An error occurred.", ephemeral=True)
    
    async def update_tournament_embed(self, interaction, tournament):
        try:
            message = interaction.message
            if message and message.embeds:
                current_count = len(tournament.players) if tournament.mode == "1v1" else len(tournament.players) // 2
                
                embed = discord.Embed(
                    title=f"<:trophy:1408575094409662474> {tournament.title} <:trophy:1408575094409662474>",
                    color=0x00ff00
                )
                
                mode_text = tournament.mode
                embed.add_field(
                    name="\u200b",
                    value=(
                        f"<:TeamSizeIcon:1413196379924336691> Players: {current_count}/{tournament.max_players}\n"
                        f"<:Abilitys:1401884706219495514> Abilityes: {tournament.abilities}\n"
                        f"<:map:1413196286500405308> Map: {tournament.map}\n"
                        f"<:target:1408580791134584893> Mode: {mode_text}\n\n"
                        f"<:Crown:1400924187325104258> **Prizes**\n"
                        f"<a:1st:1413906428850344028> 1st: {tournament.prize_1st}\n"
                        f"<a:2nd_animated:1413906496164724968> 2nd: {tournament.prize_2nd}\n"
                        f"<a:3rd_animated:1413906557997154385> 3rd: {tournament.prize_3rd}\n"
                        f"<:TrialTime:1401884029279670303> 4th: {tournament.prize_4th}\n\n"
                        f"__________\n"
                        f"**{tournament.title} Tournament Rules:**\n"
                        f"<:gift:1408573743512686623> Don't use hacks.\n"
                        f"<:gift:1408573743512686623> Don't team, only in case of 2v2.\n"
                        f"<:gift:1408573743512686623> You have 2 minutes to join.\n"
                        f"<:gift:1408573743512686623> Listen to the Hoster's decision, and don't contest.\n"
                        f"<:gift:1408573743512686623> Open a ticket to claim your prize."
                    ),
                    inline=False
                )
                
                embed.set_image(url="https://cdn.discordapp.com/attachments/1407790385685598270/1426956201656193024/Screenshot_20251012-1832592.png")
                
                await message.edit(embed=embed)
        except Exception as e:
            print(f"Error updating embed: {e}")

class HosterRegistrationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Register as Hoster", style=discord.ButtonStyle.green, custom_id="hoster_register")
    async def register_hoster(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not host_registrations['active']:
            return await interaction.response.send_message("❌ Host registration is not active.", ephemeral=True)
        
        if interaction.user in host_registrations['hosters']:
            return await interaction.response.send_message("❌ You are already registered as a hoster.", ephemeral=True)
        
        if len(host_registrations['hosters']) >= host_registrations['max_hosters']:
            return await interaction.response.send_message("❌ Maximum hosters reached.", ephemeral=True)
        
        host_registrations['hosters'].append(interaction.user)
        
        embed = discord.Embed(
            title="🎯 Hoster Registration",
            description="Register here to become a tournament hoster!",
            color=0x00ff00
        )
        
        if host_registrations['hosters']:
            hoster_list = ""
            for i, hoster in enumerate(host_registrations['hosters'], 1):
                hoster_name = hoster.name
                hoster_list += f"{i}. {hoster_name}\n"
            embed.add_field(name="Hosters registered:", value=hoster_list, inline=False)
        else:
            embed.add_field(name="Hosters registered:", value="None yet", inline=False)
        
        embed.add_field(name="Slots:", value=f"{len(host_registrations['hosters'])}/{host_registrations['max_hosters']}", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"✅ {interaction.user.name} registered as hoster.", ephemeral=True)
    
    @discord.ui.button(label="Unregister", style=discord.ButtonStyle.red, custom_id="hoster_unregister")
    async def unregister_hoster(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not host_registrations['active']:
            return await interaction.response.send_message("❌ Host registration is not active.", ephemeral=True)
        
        if interaction.user not in host_registrations['hosters']:
            return await interaction.response.send_message("❌ You are not registered as a hoster.", ephemeral=True)
        
        host_registrations['hosters'].remove(interaction.user)
        
        embed = discord.Embed(
            title="🎯 Hoster Registration",
            description="Register here to become a tournament hoster!",
            color=0x00ff00
        )
        
        if host_registrations['hosters']:
            hoster_list = ""
            for i, hoster in enumerate(host_registrations['hosters'], 1):
                hoster_name = hoster.name
                hoster_list += f"{i}. {hoster_name}\n"
            embed.add_field(name="Hosters registered:", value=hoster_list, inline=False)
        else:
          embed.add_field(name="Hosters registered:", value="None yet", inline=False)
        
        embed.add_field(name="Slots:", value=f"{len(host_registrations['hosters'])}/{host_registrations['max_hosters']}", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(f"✅ {interaction.user.name} unregistered from hosting.", ephemeral=True)

@bot.tree.command(name="tournament1v1", description="Create a 1v1 tournament")
@app_commands.describe(
    title="Tournament title (required)",
    players="Number of players (2, 4, 8, 16, or 32)",
    map="Map name",
    abilityes="Abilities setting",
    first="1st place prize",
    second="2nd place prize",
    third="3rd place prize",
    fourth="4th place prize"
)
async def tournament1v1(
    interaction: discord.Interaction,
    title: str,
    players: int,
    map: str,
    abilityes: str,
    first: str,
    second: str,
    third: str,
    fourth: str
):
    if not has_permission(interaction.user, interaction.guild.id, 'tlr') and not interaction.user.guild_permissions.manage_channels:
        return await interaction.response.send_message("❌ You don't have permission to create tournaments.", ephemeral=True)
    
    if players not in [2, 4, 8, 16, 32]:
        return await interaction.response.send_message("❌ Players must be 2, 4, 8, 16, or 32!", ephemeral=True)
    
    tournament = get_tournament(interaction.guild.id)
    tournament.__init__()
    tournament.max_players = players
    tournament.mode = "1v1"
    tournament.channel = interaction.channel
    tournament.target_channel = interaction.channel
    tournament.title = title
    tournament.map = map
    tournament.abilities = abilityes
    tournament.prize_1st = first
    tournament.prize_2nd = second
    tournament.prize_3rd = third
    tournament.prize_4th = fourth
    tournament.players = []
    tournament.eliminated = []
    tournament.active = False
    
    embed = discord.Embed(
        title=f"<:trophy:1408575094409662474> {tournament.title} <:trophy:1408575094409662474>",
        color=0x00ff00
    )
    
    embed.add_field(
        name="\u200b",
        value=(
            f"<:TeamSizeIcon:1413196379924336691> Players: 0/{players}\n"
            f"<:Abilitys:1401884706219495514> Abilityes: {abilityes}\n"
            f"<:map:1413196286500405308> Map: {map}\n"
            f"<:target:1408580791134584893> Mode: 1v1\n\n"
            f"<:Crown:1400924187325104258> **Prizes**\n"
            f"<a:1st:1413906428850344028> 1st: {first}\n"
            f"<a:2nd_animated:1413906496164724968> 2nd: {second}\n"
            f"<a:3rd_animated:1413906557997154385> 3rd: {third}\n"
            f"<:TrialTime:1401884029279670303> 4th: {fourth}\n\n"
            f"__________\n"
            f"**{tournament.title} Tournament Rules:**\n"
            f"<:gift:1408573743512686623> Don't use hacks.\n"
            f"<:gift:1408573743512686623> Don't team, only in case of 2v2.\n"
            f"<:gift:1408573743512686623> You have 2 minutes to join.\n"
            f"<:gift:1408573743512686623> Listen to the Hoster's decision, and don't contest.\n"
            f"<:gift:1408573743512686623> Open a ticket to claim your prize."
        ),
        inline=False
    )
    
    embed.set_image(url="https://cdn.discordapp.com/attachments/1407790385685598270/1426956201656193024/Screenshot_20251012-1832592.png")
    
    view = TournamentView()
    tournament.message = await interaction.channel.send(embed=embed, view=view)
    
    await log_command(interaction.guild.id, interaction.user, "/tournament1v1", f"Mode: 1v1, Max players: {players}")
    
    await interaction.response.send_message("✅ Tournament created successfully!", ephemeral=True)

@bot.tree.command(name="tournament2v2", description="Create a 2v2 tournament")
@app_commands.describe(
    title="Tournament title (required)",
    players="Number of teams (2, 4, 8, or 16)",
    map="Map name",
    abilityes="Abilities setting",
    first="1st place prize",
    second="2nd place prize",
    third="3rd place prize",
    fourth="4th place prize"
)
async def tournament2v2(
    interaction: discord.Interaction,
    title: str,
    players: int,
    map: str,
    abilityes: str,
    first: str,
    second: str,
    third: str,
    fourth: str
):
    if not has_permission(interaction.user, interaction.guild.id, 'tlr') and not interaction.user.guild_permissions.manage_channels:
        return await interaction.response.send_message("❌ You don't have permission to create tournaments.", ephemeral=True)
    
    if players not in [2, 4, 8, 16]:
        return await interaction.response.send_message("❌ Teams must be 2, 4, 8, or 16!", ephemeral=True)
    
    tournament = get_tournament(interaction.guild.id)
    tournament.__init__()
    tournament.max_players = players
    tournament.mode = "2v2"
    tournament.channel = interaction.channel
    tournament.target_channel = interaction.channel
    tournament.title = title
    tournament.map = map
    tournament.abilities = abilityes
    tournament.prize_1st = first
    tournament.prize_2nd = second
    tournament.prize_3rd = third
    tournament.prize_4th = fourth
    tournament.players = []
    tournament.eliminated = []
    tournament.active = False
    
    embed = discord.Embed(
        title=f"<:trophy:1408575094409662474> {tournament.title} <:trophy:1408575094409662474>",
        color=0x00ff00
    )
    
    embed.add_field(
        name="\u200b",
        value=(
            f"<:TeamSizeIcon:1413196379924336691> Players: 0/{players}\n"
            f"<:Abilitys:1401884706219495514> Abilityes: {abilityes}\n"
            f"<:map:1413196286500405308> Map: {map}\n"
            f"<:target:1408580791134584893> Mode: 2v2\n\n"
            f"<:Crown:1400924187325104258> **Prizes**\n"
            f"<a:1st:1413906428850344028> 1st: {first}\n"
            f"<a:2nd_animated:1413906496164724968> 2nd: {second}\n"
            f"<a:3rd_animated:1413906557997154385> 3rd: {third}\n"
            f"<:TrialTime:1401884029279670303> 4th: {fourth}\n\n"
            f"__________\n"
            f"**{tournament.title} Tournament Rules:**\n"
            f"<:gift:1408573743512686623> Don't use hacks.\n"
            f"<:gift:1408573743512686623> Don't team, only in case of 2v2.\n"
            f"<:gift:1408573743512686623> You have 2 minutes to join.\n"
            f"<:gift:1408573743512686623> Listen to the Hoster's decision, and don't contest.\n"
            f"<:gift:1408573743512686623> Open a ticket to claim your prize."
        ),
        inline=False
    )
    
    embed.set_image(url="https://cdn.discordapp.com/attachments/1407790385685598270/1426956201656193024/Screenshot_20251012-1832592.png")
    
    view = TournamentView()
    tournament.message = await interaction.channel.send(embed=embed, view=view)
    
    await log_command(interaction.guild.id, interaction.user, "/tournament2v2", f"Mode: 2v2, Max teams: {players}")
    
    await interaction.response.send_message("✅ Tournament created successfully!", ephemeral=True)

@bot.command()
async def code(ctx, member1: discord.Member, member2: discord.Member, member3: discord.Member = None, member4: discord.Member = None, *, code: str):
    try:
        await ctx.message.delete()
    except:
        pass
    
    if not has_permission(ctx.author, ctx.guild.id, 'htr') and not has_permission(ctx.author, ctx.guild.id, 'tlr') and not ctx.author.guild_permissions.manage_channels:
        return await ctx.send("❌ You don't have permission to send codes.", delete_after=5)
    
    tournament = get_tournament(ctx.guild.id)
    
    if member3 and member4 and code:
        mentions = f"{member1.mention} {member2.mention} {member3.mention} {member4.mention}"
        await ctx.send(f"{mentions} - Room Code: **{code}**")
        await log_command(ctx.guild.id, ctx.author, "!code", f"2v2 code sent: {code}")
    elif not member3 and not member4 and code:
        mentions = f"{member1.mention} {member2.mention}"
        await ctx.send(f"{mentions} - Room Code: **{code}**")
        await log_command(ctx.guild.id, ctx.author, "!code", f"1v1 code sent: {code}")
    else:
        last_arg = member3 if member3 and not member4 else member2
        if isinstance(last_arg, str):
            code = last_arg
            if member3:
                mentions = f"{member1.mention} {member2.mention}"
            else:
                mentions = f"{member1.mention}"
            await ctx.send(f"{mentions} - Room Code: **{code}**")
        else:
            await ctx.send("❌ Usage: `!code @user @user <code>` or `!code @user @user @user @user <code>`", delete_after=5)

@bot.command()
async def start(ctx):
    try:
        await ctx.message.delete()
    except:
        pass
    
    if not has_permission(ctx.author, ctx.guild.id, 'tlr') and not ctx.author.guild_permissions.manage_channels:
        return await ctx.send("❌ You don't have permission to start tournaments.", delete_after=5)
    
    tournament = get_tournament(ctx.guild.id)
    
    await log_command(ctx.guild.id, ctx.author, "!start", f"Players: {len(tournament.players)}")
    
    if tournament.max_players == 0:
        return await ctx.send("❌ No tournament has been created yet.", delete_after=5)
    
    if tournament.active:
        return await ctx.send("❌ Tournament already started.", delete_after=5)
    
    if len(tournament.players) < 2:
        return await ctx.send("❌ Not enough players to start tournament (minimum 2 players).", delete_after=5)
    
    if tournament.mode == "2v2":
        current_teams = len(tournament.players) // 2
        bots_added = 0
        while current_teams % 2 != 0:
            bot1_name = f"Bot{tournament.fake_count}"
            bot1_id = 761557952975420886 + tournament.fake_count
            bot1 = FakePlayer(bot1_name, bot1_id)
            tournament.fake_count += 1
            
            bot2_name = f"Bot{tournament.fake_count}"
            bot2_id = 761557952975420886 + tournament.fake_count
            bot2 = FakePlayer(bot2_name, bot2_id)
            tournament.fake_count += 1
            
            tournament.players.extend([bot1, bot2])
            current_teams += 1
            bots_added += 1
        
        if bots_added > 0:
            await ctx.send(f"Adding {bots_added} bot team(s) to make even bracket...", delete_after=5)
        
        team_groups = []
        processed_players = set()
        
        for player in tournament.players:
            if player in processed_players or isinstance(player, FakePlayer):
                continue
            
            team_id = get_team_id(ctx.guild.id, player.id)
            if team_id:
                teammate = get_teammate(ctx.guild.id, player.id)
                if teammate and teammate in tournament.players:
                    team_groups.append([player, teammate])
                    processed_players.add(player)
                    processed_players.add(teammate)
                else:
                    team_groups.append([player])
                    processed_players.add(player)
            else:
                team_groups.append([player])
                processed_players.add(player)
        
        fake_players = [p for p in tournament.players if isinstance(p, FakePlayer)]
        for i in range(0, len(fake_players), 2):
            if i + 1 < len(fake_players):
                team_groups.append([fake_players[i], fake_players[i+1]])
        
        random.shuffle(team_groups)
        tournament.players = []
        for team in team_groups:
            tournament.players.extend(team)
    
    else:
        bots_added = 0
        while len(tournament.players) % 2 != 0:
            bot_name = f"Bot{tournament.fake_count}"
            bot_id = 761557952975420886 + tournament.fake_count
            bot = FakePlayer(bot_name, bot_id)
            tournament.players.append(bot)
            tournament.fake_count += 1
            bots_added += 1
        
        if bots_added > 0:
            await ctx.send(f"Adding {bots_added} bot player(s) to make even bracket...", delete_after=5)
        
        random.shuffle(tournament.players)
    
    tournament.active = True
    tournament.results = []
    tournament.rounds = []
    
    if tournament.mode == "2v2":
        team_pairs = []
        for i in range(0, len(tournament.players), 4):
            team_a = [tournament.players[i], tournament.players[i+1]]
            team_b = [tournament.players[i+2], tournament.players[i+3]]
            team_pairs.append((team_a, team_b))
        tournament.rounds.append(team_pairs)
        current_round = team_pairs
    else:
        round_pairs = [(tournament.players[i], tournament.players[i+1]) for i in range(0, len(tournament.players), 2)]
        tournament.rounds.append(round_pairs)
        current_round = round_pairs
    
    embed = discord.Embed(
        title=f"<:trophy:1408575094409662474>{tournament.title} - Round 1",
        color=0x3498db
    )
    
    if tournament.mode == "2v2":
        for i, match in enumerate(current_round, 1):
            team_a, team_b = match
            team_a_display = []
            team_b_display = []
            
            guild_str = str(ctx.guild.id)
            
            for player in team_a:
                player_name = get_player_display_name(player, ctx.guild.id)
                if guild_str in bracket_roles and str(player.id) in bracket_roles[guild_str] and not isinstance(player, FakePlayer):
                    emojis = ''.join(bracket_roles[guild_str][str(player.id)])
                    player_name = f"{user.name} {emojis}"
                team_a_display.append(user.name)
            
            for player in team_b:
                player_name = get_player_display_name(player, ctx.guild.id)
                if guild_str in bracket_roles and str(player.id) in bracket_roles[guild_str] and not isinstance(player, FakePlayer):
                    emojis = ''.join(bracket_roles[guild_str][str(player.id)])
                    player_name = f"{player_name} {emojis}"
                team_b_display.append(player_name)
            
            team_a_str = " & ".join(team_a_display)
            team_b_str = " & ".join(team_b_display)
            
            embed.add_field(
                name=f" <:Abilitys:1401884706219495514> Match {i}",
                value=f"**{team_a_str}** <:vs:1400922770774163456> **{team_b_str}**",
                inline=False
            )
    else:
        for i, match in enumerate(current_round, 1):
            a, b = match
            player_a = get_player_display_name(a, ctx.guild.id)
            player_b = get_player_display_name(b, ctx.guild.id)
            
            guild_str = str(ctx.guild.id)
            if guild_str in bracket_roles and str(a.id) in bracket_roles[guild_str] and not isinstance(a, FakePlayer):
                emojis = ''.join(bracket_roles[guild_str][str(a.id)])
                player_a = f"{player_a} {emojis}"
            
            if guild_str in bracket_roles and str(b.id) in bracket_roles[guild_str] and not isinstance(b, FakePlayer):
                emojis = ''.join(bracket_roles[guild_str][str(b.id)])
                player_b = f"{player_b} {emojis}"
            
            embed.add_field(
                name=f"<:Abilitys:1401884706219495514> Match {i}",
                value=f"**{player_a}** <:vs:1400922770774163456> **{player_b}**",
                inline=False
            )
    
    embed.set_footer(text="Use !winner @player to record match results")
    embed.set_image(url="https://cdn.discordapp.com/attachments/1407790385685598270/1426956177497133066/Screenshot_20251012-1832542.png")
    
    winners_view = WinnersView(ctx.guild.id)
    tournament.message = await ctx.send(embed=embed, view=winners_view)

@bot.command()
async def restart(ctx):
    try:
        await ctx.message.delete()
    except:
        pass
    
    if not has_permission(ctx.author, ctx.guild.id, 'tlr') and not ctx.author.guild_permissions.manage_channels:
        return await ctx.send("❌ You don't have permission to restart tournaments.", delete_after=5)
    
    tournament = get_tournament(ctx.guild.id)
    
    if tournament.max_players == 0:
        return await ctx.send("❌ No tournament has been created yet.", delete_after=5)
    
    tournament.__init__()
    
    await ctx.send("✅ Tournament has been restarted! You can create a new tournament now.", delete_after=10)
    await log_command(ctx.guild.id, ctx.author, "!restart", "Tournament reset")

@bot.command()
async def winner(ctx, member: discord.Member):
    try:
        await ctx.message.delete()
    except Exception as e:
        print(f"Failed to delete message: {e}")
        pass
    
    if not has_permission(ctx.author, ctx.guild.id, 'htr') and not has_permission(ctx.author, ctx.guild.id, 'tlr') and not ctx.author.guild_permissions.manage_channels:
        return await ctx.send("❌ You don't have permission to set winners.", delete_after=5)
    
    tournament = get_tournament(ctx.guild.id)
    
    if not tournament.active:
        return await ctx.send("❌ No active tournament.", delete_after=5)
    
    current_round = tournament.rounds[-1]
    
    match_found = False
    eliminated_players = []
    match_index = -1
    winner_team = None
    loser_team = None
    
    if tournament.mode == "2v2":
        member_team_id = get_team_id(ctx.guild.id, member.id)
        if not member_team_id:
            return await ctx.send("❌ This player is not in a team.", delete_after=5)
        
        member_team = get_team_members(ctx.guild.id, member_team_id)
        
        for i, match in enumerate(current_round):
            team_a, team_b = match
            if member in team_a:
                winner_team = team_a
                loser_team = team_b
                tournament.results.append(team_a)
                eliminated_players.extend(team_b)
                match_found = True
                match_index = i
                break
            elif member in team_b:
                winner_team = team_b
                loser_team = team_a
                tournament.results.append(team_b)
                eliminated_players.extend(team_a)
                match_found = True
                match_index = i
                break
        
        if match_found:
            winner_name = get_team_display_name(ctx.guild.id, winner_team)
            round_number = len(tournament.rounds)
            match_key = f"round_{round_number}_match_{match_index + 1}"
            tournament.match_winners[match_key] = winner_team
    
    else:
        for i, match in enumerate(current_round):
            a, b = match
            if member == a or member == b:
                tournament.results.append(member)
                eliminated_players.extend([a if member == b else b])
                match_found = True
                match_index = i
                break
        
        if match_found:
            winner_name = get_player_display_name(member, ctx.guild.id)
            round_number = len(tournament.rounds)
            match_key = f"round_{round_number}_match_{match_index + 1}"
            tournament.match_winners[match_key] = member
    
    if not match_found:
        return await ctx.send("❌ This player/team is not in the current round.", delete_after=5)
    
    tournament.eliminated.extend(eliminated_players)
    
    if len(tournament.results) == len(current_round):
        if len(tournament.results) == 1:
            winner_data = tournament.results[0]
            
            all_eliminated = tournament.eliminated
            
            placements = []
            
            placements.append((1, winner_data))
            
            if len(all_eliminated) >= 1:
                placements.append((2, all_eliminated[-1]))
            
            if len(all_eliminated) >= 2:
                placements.append((3, all_eliminated[-2]))
            if len(all_eliminated) >= 3:
                placements.append((4, all_eliminated[-3]))
            
            winner_display = get_player_display_name(winner_data, ctx.guild.id)
            
            embed = discord.Embed(
            
            results_display = "<:Leaderboard:1406282721436762244>Top 4<:Leaderboard:1406282721436762244>\n"
            for place, player_obj in placements[:4]:
                player_str = get_player_display_name(player_obj, ctx.guild.id)
                if place == 1:
                    results_display += f"<a:1st:1413906428850344028>1st: {player_str}\n"
                elif place == 2:
                    results_display += f"<a:2nd_animated:1413906496164724968>2nd: {player_str}\n"
                elif place == 3:
                    results_display += f"<a:3rd_animated:1413906557997154385>3rd: {player_str}\n"
                elif place == 4:
                    results_display += f"<:TimeTrial:1401999416688382096>4th: {player_str}\n"
            
            results_display += "\n<:star:1413871338803822684>Congrats!"
            
            embed.add_field(name="\u200b", value=results_display, inline=False)
            
            
            embed.add_field(name="\u200b", value=prize_text, inline=False)
            
            winner_player_obj = winner_data
            if hasattr(winner_player_obj, 'display_avatar') and not isinstance(winner_player_obj, FakePlayer):
                embed.set_thumbnail(url=winner_player_obj.display_avatar.url)
            
            embed.set_footer(text=f"Tournament completed • {datetime.now().strftime('%d.%m.%Y %H:%M')}")
            embed.set_image(url="https://cdn.discordapp.com/attachments/1407790385685598270/1426956154688377002/Screenshot_20251012-1832422.png")
            
            completed_view = discord.ui.View()
            await ctx.send(embed=embed, view=completed_view)
            
            tournament.__init__()
        else:
            next_round_winners = tournament.results.copy()
            
            while len(next_round_winners) % 2 != 0:
                bot_name = f"Bot{tournament.fake_count}"
                bot_id = 761557952975420886 + tournament.fake_count
                bot = FakePlayer(bot_name, bot_id)
                next_round_winners.append(bot)
                tournament.fake_count += 1
            
            next_round_pairs = []
            for i in range(0, len(next_round_winners), 2):
                next_round_pairs.append((next_round_winners[i], next_round_winners[i+1]))
            
            tournament.rounds.append(next_round_pairs)
            tournament.results = []
            
            round_num = len(tournament.rounds)
            embed = discord.Embed(
                title=f"🏆 {tournament.title} - Round {round_num}",
                description=f"**Map:** {tournament.map}\n**Abilities:** {tournament.abilities}",
                color=0x3498db
            )
            
            if tournament.mode == "2v2":
                for i, match in enumerate(next_round_pairs, 1):
                    team_a, team_b = match
                    team_a_display = []
                    team_b_display = []
                    
                    guild_str = str(ctx.guild.id)
                    
                    for player in team_a:
                        player_name = get_player_display_name(player, ctx.guild.id)
                        if guild_str in bracket_roles and str(player.id) in bracket_roles[guild_str] and not isinstance(player, FakePlayer):
                            emojis = ''.join(bracket_roles[guild_str][str(player.id)])
                            player_name = f"{player_name} {emojis}"
                        team_a_display.append(player_name)
                    
                    for player in team_b:
                        player_name = get_player_display_name(player, ctx.guild.id)
                        if guild_str in bracket_roles and str(player.id) in bracket_roles[guild_str] and not isinstance(player, FakePlayer):
                            emojis = ''.join(bracket_roles[guild_str][str(player.id)])
                            player_name = f"{player_name} {emojis}"
                        team_b_display.append(player_name)
                    
                    team_a_str = " & ".join(team_a_display)
                    team_b_str = " & ".join(team_b_display)
                    
                    embed.add_field(
                        name=f"⚔️ Match {i}",
                        value=f"**{team_a_str}** <:VS:1402690899485655201> **{team_b_str}**",
                        inline=False
                    )
            else:
                for i, match in enumerate(next_round_pairs, 1):
                    a, b = match
                    player_a = get_player_display_name(a, ctx.guild.id)
                    player_b = get_player_display_name(b, ctx.guild.id)
                    
                    guild_str = str(ctx.guild.id)
                    if guild_str in bracket_roles and str(a.id) in bracket_roles[guild_str] and not isinstance(a, FakePlayer):
                        emojis = ''.join(bracket_roles[guild_str][str(a.id)])
                        player_a = f"{player_a} {emojis}"
                    
                    if guild_str in bracket_roles and str(b.id) in bracket_roles[guild_str] and not isinstance(b, FakePlayer):
                        emojis = ''.join(bracket_roles[guild_str][str(b.id)])
                        player_b = f"{player_b} {emojis}"
                    
                    embed.add_field(
                        name=f"⚔️ Match {i}",
                        value=f"**{player_a}** <:VS:1402690899485655201> **{player_b}**",
                        inline=False
                    )
            
            embed.set_footer(text="Use !winner @player to record match results")
            embed.set_image(url="https://cdn.discordapp.com/attachments/1407790385685598270/1426956177497133066/Screenshot_20251012-1832542.png")
            
            next_round_winners_view = WinnersView(ctx.guild.id)
            tournament.message = await ctx.send(embed=embed, view=next_round_winners_view)
    
    await ctx.send(f"✅ {winner_name} wins their match!", delete_after=5)

@bot.command()
async def fake(ctx, number: int = 1):
    try:
        await ctx.message.delete()
    except:
        pass
    
    if not has_permission(ctx.author, ctx.guild.id, 'tlr') and not ctx.author.guild_permissions.manage_channels:
        return await ctx.send("❌ You don't have permission to add fake players.", delete_after=5)
    
    tournament = get_tournament(ctx.guild.id)
    
    if tournament.max_players == 0:
        return await ctx.send("❌ No tournament has been created yet.", delete_after=5)
    
    if tournament.active:
        return await ctx.send("❌ Cannot add fake players after tournament has started.", delete_after=5)
    
    if number < 1 or number > 10:
        return await ctx.send("❌ Number must be between 1 and 10.", delete_after=5)
    
    for _ in range(number):
        if len(tournament.players) >= tournament.max_players:
            break
        
        bot_name = f"Bot{tournament.fake_count}"
        bot_id = 761557952975420886 + tournament.fake_count
        bot = FakePlayer(bot_name, bot_id)
        tournament.players.append(bot)
        tournament.fake_count += 1
    
    await ctx.send(f"✅ Added {number} fake player(s)! Current players: {len(tournament.players)}/{tournament.max_players}", delete_after=10)
    await log_command(ctx.guild.id, ctx.author, "!fake", f"Added {number} fake players")

@bot.command()
async def hosterregist(ctx, max_hosters: int):
    try:
        await ctx.message.delete()
    except:
        pass
    
    if not has_permission(ctx.author, ctx.guild.id, 'tlr') and not ctx.author.guild_permissions.manage_channels:
        return await ctx.send("❌ You don't have permission to start host registration.", delete_after=5)
    
    host_registrations['active'] = True
    host_registrations['max_hosters'] = max_hosters
    host_registrations['hosters'] = []
    host_registrations['channel'] = ctx.channel
    
    embed = discord.Embed(
        title="🎯 Hoster Registration",
        description="Register here to become a tournament hoster!",
        color=0x00ff00
    )
    
    embed.add_field(name="Hosters registered:", value="None yet", inline=False)
    embed.add_field(name="Slots:", value=f"0/{max_hosters}", inline=True)
    
    view = HosterRegistrationView()
    host_registrations['message'] = await ctx.send(embed=embed, view=view)
    
    await log_command(ctx.guild.id, ctx.author, "!hosterregist", f"Max hosters: {max_hosters}")

@bot.command()
async def ticket(ctx):
    try:
        await ctx.message.delete()
    except:
        pass
    
    await ctx.send("🎫 Ticket system placeholder. Configure your ticket system here.", delete_after=10)

@bot.command()
async def alllogs(ctx, channel: discord.TextChannel):
    if not ctx.author.guild_permissions.manage_guild:
        return await ctx.send("❌ You don't have permission to set logs channel.", delete_after=5)
    try:
        await ctx.message.delete()
    except:
        pass
    
    guild_str = str(ctx.guild.id)
    log_channels[guild_str] = channel.id
    save_data()
    
    embed = discord.Embed(
        title="<:bracketrole:1413196441564315810> Bracket Roles",
        color=0x9b59b6
    )
    
    if guild_str in bracket_roles and bracket_roles[guild_str]:
        roles_text = ""
        for user_id, emojis in bracket_roles[guild_str].items():
            try:
                member = ctx.guild.get_member(int(user_id))
                if member:
                    emojis_str = ''.join(emojis)
                    roles_text += f"{member.mention}: {emojis_str}\n"
            except:
                pass
        
        if roles_text:
            embed.description = roles_text
        else:
            embed.description = "No bracket roles assigned yet."
    else:
        embed.description = "No bracket roles assigned yet."
    
    await channel.send(embed=embed)
    
    await ctx.send(f"✅ Logs channel set to {channel.mention}", delete_after=10)
    await log_command(ctx.guild.id, ctx.author, "!alllogs", f"Logs channel set to {channel.mention}")

@bot.command()
async def bracketrole(ctx, member: discord.Member, emoji1: str, emoji2: str = "", emoji3: str = ""):
    if not ctx.author.guild_permissions.manage_guild:
        return await ctx.send("❌ You don't have permission to set bracket roles.", delete_after=5)
    try:
        await ctx.message.delete()
    except:
        pass
    
    guild_str = str(ctx.guild.id)
    user_str = str(member.id)
    
    if guild_str not in bracket_roles:
        bracket_roles[guild_str] = {}
    
    emojis = [emoji1]
    if emoji2:
        emojis.append(emoji2)
    if emoji3:
        emojis.append(emoji3)
    
    bracket_roles[guild_str][user_str] = emojis
    save_data()
    
    await ctx.send(f"✅ Bracket role set for {member.name}: {' '.join(emojis)}", delete_after=10)
    await log_command(ctx.guild.id, ctx.author, "!bracketrole", f"Set bracket role for {member.name}")
    
    await auto_update_alllogs(ctx.guild)

@bot.command()
async def bracketrolereset(ctx, member: discord.Member = None):
    if not ctx.author.guild_permissions.manage_guild:
        return await ctx.send("❌ You don't have permission to reset bracket roles.", delete_after=5)
    try:
        await ctx.message.delete()
    except:
        pass
    
    guild_str = str(ctx.guild.id)
    
    if member:
        user_str = str(member.id)
        if guild_str in bracket_roles and user_str in bracket_roles[guild_str]:
            del bracket_roles[guild_str][user_str]
            save_data()
            await ctx.send(f"✅ Bracket role reset for {member.name}", delete_after=10)
        else:
            await ctx.send(f"❌ {member.name} has no bracket role.", delete_after=5)
    else:
        if guild_str in bracket_roles:
            bracket_roles[guild_str] = {}
            save_data()
            await ctx.send("✅ All bracket roles reset.", delete_after=10)
        else:
            await ctx.send("❌ No bracket roles to reset.", delete_after=5)
    
    await log_command(ctx.guild.id, ctx.author, "!bracketrolereset", "Reset bracket roles")
    
    await auto_update_alllogs(ctx.guild)

@bot.command()
async def invite(ctx, member: discord.Member):
    try:
        await ctx.message.delete()
    except:
        pass
    
    if member == ctx.author:
        return await ctx.send("❌ You cannot invite yourself.", delete_after=5)
    
    if member.bot:
        return await ctx.send("❌ You cannot invite bots.", delete_after=5)
    
    guild_str = str(ctx.guild.id)
    author_str = str(ctx.author.id)
    member_str = str(member.id)
    
    author_team_id = get_team_id(ctx.guild.id, ctx.author.id)
    if author_team_id:
        return await ctx.send("❌ You are already in a team. Use `!leave_team` first.", delete_after=5)
    
    member_team_id = get_team_id(ctx.guild.id, member.id)
    if member_team_id:
        return await ctx.send(f"❌ {member.name} is already in a team.", delete_after=5)
    
    if guild_str not in team_invitations:
        team_invitations[guild_str] = {}
    
    if member_str not in team_invitations[guild_str]:
        team_invitations[guild_str][member_str] = []
    
    if ctx.author.id in team_invitations[guild_str][member_str]:
        return await ctx.send(f"❌ You already sent an invitation to {member.name}.", delete_after=5)
    
    team_invitations[guild_str][member_str].append(ctx.author.id)
    
    try:
        invite_view = InviteView(ctx.author, ctx.guild.id)
        await member.send(f"{ctx.author.name} invited you to be their teammate!", view=invite_view)
        await ctx.send(f"✅ Invitation sent to {member.name} via DM!", delete_after=10)
        await log_command(ctx.guild.id, ctx.author, "!invite", f"Sent invitation to {member.name}")
    except discord.Forbidden:
        await ctx.send(f"❌ Cannot send DM to {member.name}. They may have DMs disabled.", delete_after=10)

@bot.command()
async def leave_team(ctx):
    try:
        await ctx.message.delete()
    except:
        pass
    
    team_id = get_team_id(ctx.guild.id, ctx.author.id)
    
    if not team_id:
        return await ctx.send("❌ You are not in a team.", delete_after=5)
    
    teammate = get_teammate(ctx.guild.id, ctx.author.id)
    
    remove_team(ctx.guild.id, team_id)
    
    if teammate:
        await ctx.send(f"✅ You left the team with {teammate.name}.", delete_after=10)
        await log_command(ctx.guild.id, ctx.author, "!leave_team", f"Left team with {teammate.name}")
    else:
        await ctx.send("✅ You left your team.", delete_after=10)

@bot.command()
async def update(ctx):
    try:
        await ctx.message.delete()
    except:
        pass
    
    if not ctx.author.guild_permissions.manage_guild:
        return await ctx.send("❌ You don't have permission to update logs.", delete_after=5)
    
    guild_str = str(ctx.guild.id)
    
    if guild_str in log_channels:
        await auto_update_alllogs(ctx.guild)
        await ctx.send("✅ Logs updated!", delete_after=5)
    else:
        channel = ctx.channel
        async for message in channel.history(limit=100):
            if message.author == bot.user and message.embeds:
                embed = message.embeds[0]
                if embed.title and "Bracket Roles" in embed.title:
                    new_embed = discord.Embed(
                        title="<:bracketrole:1413196441564315810> Bracket Roles",
                        color=0x9b59b6
                    )
                    
                    if guild_str in bracket_roles and bracket_roles[guild_str]:
                        roles_text = ""
                        for user_id, emojis in bracket_roles[guild_str].items():
                            try:
                                member = ctx.guild.get_member(int(user_id))
                                if member:
                                    emojis_str = ''.join(emojis)
                                    roles_text += f"{member.mention}: {emojis_str}\n"
                            except:
                                pass
                        
                        if roles_text:
                            new_embed.description = roles_text
                        else:
                            new_embed.description = "No bracket roles assigned yet."
                    else:
                        new_embed.description = "No bracket roles assigned yet."
                    
                    await message.edit(embed=new_embed)
                    await ctx.send("✅ Logs updated!", delete_after=5)
                    return
        
        await ctx.send("❌ No bracket roles message found in this channel.", delete_after=5)

if __name__ == '__main__':
    if not TOKEN:
        print('Error: TOKEN environment variable not set!')
        print('Please set your Discord bot token in the Secrets tab.')
        exit(1)
    
    try:
        bot.run(TOKEN)
    except discord.PrivilegedIntentsRequired:
        print('\n' + '='*60)
        print('ERROR: Privileged Intents Required!')
        print('='*60)
        print('\nYou need to enable the following intents in Discord Developer Portal:')
        print('1. Go to https://discord.com/developers/applications')
        print('2. Select your bot application')
        print('3. Go to the "Bot" section')
        print('4. Scroll down to "Privileged Gateway Intents"')
        print('5. Enable these intents:')
        print('   ✓ SERVER MEMBERS INTENT')
        print('   ✓ MESSAGE CONTENT INTENT')
        print('6. Save changes and restart the bot')
        print('='*60 + '\n')
        exit(1)

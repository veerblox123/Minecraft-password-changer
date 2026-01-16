import discord
from discord import app_commands
from discord.ext import commands
import os
from dotenv import load_dotenv
from browser_automation import BrowserAutomation

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True 

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self):
        # Explicitly add the command to the tree
        print("🛠️ Manually adding /cpass to the command tree...")
        self.tree.add_command(cpass_command)

bot = MyBot()

# Define the command outside the class so it's easier to manage
@app_commands.command(name="cpass", description="Bypass passkeys and sign in")
@app_commands.describe(email="Account email", password="Current password", new_password="New password")
async def cpass_command(interaction: discord.Interaction, email: str, password: str, new_password: str):
    await interaction.response.defer(ephemeral=True)
    automation = BrowserAutomation()
    
    try:
        await automation.start()
        await interaction.followup.send(f"🚀 Attempting login for `{email}`...")
        
        success = await automation.login(email, password)
        
        if not success:
            if os.path.exists("login_error.png"):
                file = discord.File("login_error.png")
                await interaction.followup.send("❌ Login failed. See screenshot:", file=file)
            else:
                await interaction.followup.send("❌ Login failed. Passkey could not be bypassed.")
            return

        await interaction.followup.send("✅ Login successful! Browser is now inside the account.")

    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")
    finally:
        await automation.close()

@bot.event
async def on_ready():
    print(f'✅ {bot.user} is online!')
    try:
        # Syncing globally
        synced = await bot.tree.sync()
        print(f"🔄 Successfully synced {len(synced)} command(s).")
        for cmd in synced:
            print(f"   -> Found command: /{cmd.name}")
    except Exception as e:
        print(f"❌ Sync error: {e}")

if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
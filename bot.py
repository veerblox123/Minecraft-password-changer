import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import io
import traceback
from dotenv import load_dotenv
from browser_automation import BrowserAutomation

# Load environment variables from .env file
load_dotenv()

# --- Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Store active browser sessions and pending captchas
active_sessions = {}
pending_captchas = {} 

@bot.event
async def on_ready():
    print(f'✅ {bot.user} has logged in!')
    try:
        synced = await bot.tree.sync()
        print(f"🔄 Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

@bot.event
async def on_message(message):
    # Handle Captcha Responses (Replies to the captcha image)
    if message.reference and message.author.id in pending_captchas:
        automation, interaction, captcha_msg, email, new_password = pending_captchas[message.author.id]
        
        if message.reference.message_id == captcha_msg.id:
            captcha_code = message.content.strip()
            if captcha_code:
                await message.add_reaction("✅")
                await interaction.followup.send(f"🔐 Received captcha code: `{captcha_code}`. Processing...")
                
                try:
                    await automation.fill_captcha(captcha_code)
                    await interaction.followup.send("✅ Captcha filled! Moving to verification...")
                    await automation.click_next_after_captcha()
                    
                    # Clean up and proceed
                    del pending_captchas[message.author.id]
                    await continue_after_captcha(automation, interaction, email, new_password)
                except Exception as e:
                    await interaction.followup.send(f"❌ Error filling captcha: {str(e)}")
                    del pending_captchas[message.author.id]
                    if automation:
                        await automation.close()
    
    await bot.process_commands(message)

async def continue_after_captcha(automation, interaction, email, new_password):
    """Handles the final steps: Scrapes code and changes password"""
    try:
        # Get metadata gathered before the captcha
        account_info = getattr(automation, 'account_info', {})
        address_info = getattr(automation, 'address_info', {})
        payment_info = getattr(automation, 'payment_info', {})
        xbox_username = getattr(automation, 'xbox_username', '')
        sent_emails = getattr(automation, 'sent_emails', [])
        skype_name = getattr(automation, 'skype_name', '')
        
        await interaction.followup.send("⏳ Waiting for Outlook verification code (this may take 10-60s)...")
        
        verification_code = None
        for attempt in range(6):
            await asyncio.sleep(10)
            verification_code = await automation.scrape_verification_code()
            if verification_code:
                await interaction.followup.send("✅ Verification code found!")
                break
            if attempt < 5:
                await interaction.followup.send(f"⏳ Still checking... (attempt {attempt + 1}/6)")
        
        if not verification_code:
            await interaction.followup.send("❌ Timeout: Could not find verification code.")
            return
        
        await interaction.followup.send("✍️ Filling verification details and finalizing...")
        await automation.fill_verification_and_details(
            verification_code, account_info, address_info, 
            payment_info, xbox_username, sent_emails, skype_name
        )
        
        await interaction.followup.send("🔄 Changing password now...")
        success = await automation.change_password(new_password)
        
        if success:
            await interaction.followup.send(f"✅ **Password changed successfully!**\nNew password: `{new_password}`")
        else:
            await interaction.followup.send("❌ Password change failed at the final step.")
            
    except Exception as e:
        await interaction.followup.send(f"❌ An error occurred: {str(e)}")
        traceback.print_exc()
    finally:
        if automation:
            await automation.close()

@bot.tree.command(name="cpass", description="Automated Microsoft password change process")
@app_commands.describe(
    email="Microsoft account email",
    password="Current password",
    new_password="Expected new password",
    captcha="Captcha code (optional)"
)
async def cpass(interaction: discord.Interaction, email: str, password: str, new_password: str, captcha: str = None):
    await interaction.response.defer(ephemeral=True)
    
    automation = None
    try:
        await interaction.followup.send("🚀 Initializing browser automation...")
        automation = BrowserAutomation()
        await automation.start()
        active_sessions[interaction.user.id] = automation
        
        await interaction.followup.send("📝 Logging in...")
        if not await automation.login(email, password):
            await interaction.followup.send("❌ Login failed. Check credentials.")
            return
        
        # Scrape required info before heading to recovery
        await interaction.followup.send("🔍 Gathering account data (Xbox, Payments, Emails)...")
        automation.account_info = await automation.scrape_account_info()
        automation.address_info = await automation.scrape_addresses()
        automation.payment_info = await automation.scrape_payment_methods()
        automation.xbox_username = await automation.scrape_xbox_username()
        automation.sent_emails = await automation.scrape_sent_emails()
        automation.skype_name = await automation.scrape_skype_name()
        
        await interaction.followup.send("🔐 Navigating to recovery page...")
        captcha_info = await automation.navigate_to_account_recovery(email, interaction)
        
        # Check if we hit a Captcha wall
        if captcha_info and captcha_info.get('needs_captcha'):
            captcha_image = await automation.get_captcha_image()
            if captcha_image:
                file = discord.File(io.BytesIO(captcha_image), filename="captcha.png")
                captcha_msg = await interaction.followup.send(
                    "⚠️ **Captcha Required!**\nReply to this message with the code in the image:",
                    file=file
                )
                pending_captchas[interaction.user.id] = (automation, interaction, captcha_msg, email, new_password)
                return 
            
            # If no automated image found but user didn't provide one in command
            if not captcha:
                await interaction.followup.send("⚠️ Captcha required. Re-run command with the `captcha:` parameter.")
                return

        # If captcha was provided in the command directly
        if captcha:
            await automation.fill_captcha(captcha)
            await automation.click_next_after_captcha()
        
        # Proceed to the email phase
        await continue_after_captcha(automation, interaction, email, new_password)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Critical Error: {str(e)}")
        traceback.print_exc()
        if automation:
            await automation.close()
    finally:
        if interaction.user.id in active_sessions:
            del active_sessions[interaction.user.id]

if __name__ == "__main__":
    # Get token from .env
    token = os.getenv("DISCORD_TOKEN")
    
    if not token:
        print("❌ FATAL: DISCORD_TOKEN not found in .env file.")
    else:
        print("✅ Starting bot...")
        bot.run(token)
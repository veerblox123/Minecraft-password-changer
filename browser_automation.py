from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import asyncio
import os

class BrowserAutomation:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        
    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        self.page = await self.context.new_page()
        
    async def login(self, email: str, password: str) -> bool:
        try:
            print(f"🌐 Navigating to login for: {email}")
            await self.page.goto("https://login.live.com", wait_until="networkidle", timeout=60000)
            
            # 1. Fill Email
            email_input = await self.page.wait_for_selector('input[type="email"], #i0116', timeout=20000)
            await email_input.fill(email)
            await self.page.keyboard.press("Enter")
            
            # 2. Handle Passkey / "Sign in another way" screens
            print("⏳ Detecting next screen (Bypassing Passkeys)...")
            for _ in range(40):
                # Target the "Use your password" button from your screenshot
                if await self.page.is_visible('text="Use your password"'):
                    print("🔘 Clicking 'Use your password' option...")
                    await self.page.click('text="Use your password"')
                    await asyncio.sleep(2)
                    break

                # If it goes directly to the "Face, fingerprint" screen, click Back
                if await self.page.is_visible('text="Face, fingerprint, PIN or security key"'):
                    print("🚫 Security key screen detected! Clicking Back...")
                    await self.page.click('#idBtn_Back')
                    await asyncio.sleep(2)

                if await self.page.is_visible('input[name="passwd"], #i0118'):
                    break
                
                await asyncio.sleep(0.5)

            # 3. Fill Password
            pwd_selector = 'input[name="passwd"], #i0118'
            password_input = await self.page.wait_for_selector(pwd_selector, state="visible", timeout=20000)
            await password_input.fill(password)
            await asyncio.sleep(1)
            await self.page.keyboard.press("Enter")
            
            # 4. Handle "Stay Signed In" (KMSI)
            for _ in range(15):
                if "account.microsoft.com" in self.page.url:
                    return True
                kmsi = await self.page.query_selector('#idSIButton9')
                if kmsi and await kmsi.is_visible():
                    await kmsi.click()
                await asyncio.sleep(1)

            return "login.live.com" not in self.page.url
        except Exception as e:
            print(f"Login error: {e}")
            await self.page.screenshot(path="login_error.png")
            return False

    async def close(self):
        if self.browser: await self.browser.close()
        if self.playwright: await self.playwright.stop()
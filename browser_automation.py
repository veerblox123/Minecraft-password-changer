from playwright.async_api import async_playwright
import asyncio

class BrowserAutomation:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        
    async def start(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=False) # Keep False to watch it work
        self.context = await self.browser.new_context(viewport={'width': 1280, 'height': 720})
        self.page = await self.context.new_page()
        
    async def login(self, email: str, password: str) -> bool:
        try:
            print(f"🌐 Navigating to login for: {email}")
            await self.page.goto("https://login.live.com", wait_until="networkidle")
            
            # Step 1: Email Entry
            await self.page.fill('input[type="email"]', email)
            await self.page.keyboard.press("Enter")
            
            # Friend's 2000ms delay for security redirects
            print("⏳ Waiting 2000ms for security screens...")
            await asyncio.sleep(2)

            # Step 2: Handle Passkey/Error screen loops
            for _ in range(25):
                # If password field is visible, break and fill it
                if await self.page.is_visible('input[name="passwd"]'):
                    break

                # FIXED: Check visibility of the "Sign in another way" link (Images 11 & 12)
                error_link = self.page.get_by_text("Sign in another way").first
                if await error_link.is_visible():
                    print("🔗 Error screen detected. Clicking 'Sign in another way'...")
                    await error_link.click()
                    await asyncio.sleep(2)
                    continue

                # FIXED: Check visibility of the "Use your password" box (Image 1)
                pwd_btn = self.page.get_by_text("Use your password").first
                if await pwd_btn.is_visible():
                    print("🔘 Selecting 'Use your password'...")
                    await pwd_btn.click()
                    await asyncio.sleep(2)
                    continue
                
                # FIXED: Handle the loading bar/System Prompt (Images 2 & 13)
                sys_prompt = self.page.get_by_text("Face, fingerprint").first
                if await sys_prompt.is_visible():
                    print("🚫 System prompt detected. Clicking Back...")
                    await self.page.click('#idBtn_Back')
                    await asyncio.sleep(2)

                await asyncio.sleep(1)

            # Step 3: Entering Password
            print("⌨️ Entering current password...")
            await self.page.fill('input[name="passwd"]', password)
            await self.page.keyboard.press("Enter")
            await asyncio.sleep(2)

            # Step 4: Handle "Stay Signed In"
            kmsi = self.page.locator('#idSIButton9')
            if await kmsi.is_visible():
                await kmsi.click()
            
            # Final verification
            await self.page.wait_for_url("https://account.microsoft.com/**", timeout=30000)
            print("✅ Successfully logged in!")
            return True

        except Exception as e:
            print(f"❌ Login error: {e}")
            await self.page.screenshot(path="login_error.png")
            return False

    async def close(self):
        if self.browser: await self.browser.close()
        if self.playwright: await self.playwright.stop()
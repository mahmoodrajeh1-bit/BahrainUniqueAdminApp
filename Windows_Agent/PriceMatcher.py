
import csv
import json
import os
import re
import sys
import time
import threading
import tkinter as tk
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tkinter import messagebox, scrolledtext
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

APP_TITLE = "SharafDG Price Matcher"
OFFERS_URL = "https://sellerhub.sharafdg.com/offers/all-offers"

INPUT_SELECTOR = "input.offers-grid-sale-price-inputbox"
UPDATE_SELECTOR = "button.offers-grid-btn-update"
NEXT_SELECTOR = "button.btn-go-forward"
SKU_SELECTOR = "span.hover-copy-icon.mr-15"

ROW_WAIT_MS = 1000
PAGE_WAIT_MS = 1800
MAX_PAGES = 500
MAX_RETRIES = 3

def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

BASE_DIR = app_dir()
SPECIAL_SKUS_FILE = BASE_DIR / "special_skus.txt"
LOG_DIR = BASE_DIR / "logs"
STATE_FILE = BASE_DIR / "pricing_state.json"
CHECKPOINT_FILE = BASE_DIR / "resume_checkpoint.json"

def detect_chrome() -> str | None:
    candidates = [
        Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
    ]
    for path in candidates:
        if path and path.exists():
            return str(path)
    return None

def default_user_data_dir(executable: str) -> str:
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    if "msedge" in executable.lower():
        return str(local / "Microsoft/Edge/User Data")
    return str(local / "Google/Chrome/User Data")

def load_special_skus() -> set[str]:
    if not SPECIAL_SKUS_FILE.exists():
        SPECIAL_SKUS_FILE.write_text(
            "# Put one SKU per line.\n# Example:\n# S200791364\n",
            encoding="utf-8",
        )
    result = set()
    for raw in SPECIAL_SKUS_FILE.read_text(encoding="utf-8-sig").splitlines():
        sku = raw.strip().upper()
        if not sku or sku.startswith("#"):
            continue
        result.add(sku)
    return result

def clean_price(value: str | None) -> Decimal | None:
    if value is None:
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", str(value).replace(",", ""))
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None

def format_price(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.001')):.3f}"

class PriceMatcherApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("860x650")

        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.worker = None

        self.stats = {
            "cycle": 0,
            "page": 0,
            "checked": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "current_sku": "",
            "last_action": "",
        }

        tk.Label(root, text=APP_TITLE, font=("Segoe UI", 17, "bold")).pack(pady=(12, 4))

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(root, textvariable=self.status_var, font=("Segoe UI", 10)).pack(pady=(0, 8))

        options = tk.LabelFrame(root, text="Continuous Repricing Settings", padx=10, pady=8)
        options.pack(fill=tk.X, padx=12, pady=6)

        self.continuous_var = tk.BooleanVar(value=True)
        self.continue_errors_var = tk.BooleanVar(value=True)
        self.retry_var = tk.BooleanVar(value=True)
        self.adaptive_var = tk.BooleanVar(value=True)
        self.dry_run_var = tk.BooleanVar(value=False)
        self.interval_var = tk.StringVar(value="1")

        tk.Checkbutton(options, text="Run continuously", variable=self.continuous_var).grid(row=0, column=0, sticky="w", padx=5, pady=4)
        tk.Checkbutton(options, text="Continue after errors", variable=self.continue_errors_var).grid(row=0, column=1, sticky="w", padx=5, pady=4)
        tk.Checkbutton(options, text="Auto retry failed updates", variable=self.retry_var).grid(row=0, column=2, sticky="w", padx=5, pady=4)
        tk.Checkbutton(options, text="Adaptive waiting", variable=self.adaptive_var).grid(row=1, column=0, sticky="w", padx=5, pady=4)
        tk.Checkbutton(options, text="Dry Run (do not change prices)", variable=self.dry_run_var).grid(row=2, column=0, sticky="w", padx=5, pady=4)

        tk.Label(options, text="Base interval (minutes):").grid(row=1, column=1, sticky="e", padx=(5, 2), pady=4)
        tk.Entry(options, width=8, textvariable=self.interval_var).grid(row=1, column=2, sticky="w", padx=2, pady=4)

        tk.Label(
            options,
            text="Adaptive mode: 1 minute after updates, 3 minutes if nothing changed.",
            font=("Segoe UI", 8),
        ).grid(row=3, column=0, columnspan=3, sticky="w", padx=5, pady=(2, 0))

        buttons = tk.Frame(root)
        buttons.pack(pady=6)

        self.start_btn = tk.Button(buttons, text="Start", width=13, command=self.start)
        self.start_btn.grid(row=0, column=0, padx=5)

        self.pause_btn = tk.Button(buttons, text="Pause", width=13, state=tk.DISABLED, command=self.toggle_pause)
        self.pause_btn.grid(row=0, column=1, padx=5)

        self.stop_btn = tk.Button(buttons, text="Stop", width=13, state=tk.DISABLED, command=self.stop)
        self.stop_btn.grid(row=0, column=2, padx=5)

        self.open_skus_btn = tk.Button(buttons, text="Open special_skus.txt", width=22, command=self.open_skus)
        self.open_skus_btn.grid(row=0, column=3, padx=5)

        self.log_box = scrolledtext.ScrolledText(root, height=27, font=("Consolas", 9))
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        footer = (
            "Special SKUs: Lowest Price - 0.001 | Other SKUs: Match Lowest Price exactly\n"
            "Uses a dedicated browser profile. Chrome/Edge may remain open."
        )
        tk.Label(root, text=footer, justify=tk.CENTER, font=("Segoe UI", 9)).pack(pady=(0, 10))

    def log(self, text: str):
        stamp = time.strftime("%H:%M:%S")
        line = f"[{stamp}] {text}\n"
        LOG_DIR.mkdir(exist_ok=True)
        try:
            with (LOG_DIR / f"{time.strftime('%Y-%m-%d')}.log").open("a", encoding="utf-8") as daily:
                daily.write(line)
        except OSError:
            pass
        self.stats["last_action"] = text
        self.root.after(0, lambda: self._append_log(line))

    def _append_log(self, line: str):
        self.log_box.insert(tk.END, line)
        self.log_box.see(tk.END)

    def update_status(self):
        s = self.stats
        text = (
            f"Cycle {s['cycle']} | Page {s['page']} | Checked {s['checked']} | "
            f"Updated {s['updated']} | Skipped {s['skipped']} | Errors {s['errors']}"
        )
        self.root.after(0, lambda: self.status_var.set(text))

    def open_skus(self):
        load_special_skus()
        os.startfile(SPECIAL_SKUS_FILE)

    def start(self):
        if self.worker and self.worker.is_alive():
            return

        try:
            interval = float(self.interval_var.get())
            if interval <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror(APP_TITLE, "Enter a valid interval greater than 0 minutes.")
            return

        if not messagebox.askyesno(
            APP_TITLE,
            "This will make real price changes in Seller Hub.\n\n"
            "Special SKUs: Lowest Price - 0.001\n"
            "Other SKUs: Match Lowest Price exactly\n\n"
            "Continue?"
        ):
            return

        # A manual Start always begins a brand-new run from page 1.
        self.clear_checkpoint()
        self.stop_event.clear()
        self.pause_event.clear()
        self.stats = {"cycle": 0, "page": 0, "checked": 0, "updated": 0, "skipped": 0, "errors": 0, "current_sku": "", "last_action": ""}

        self.start_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.NORMAL, text="Pause")
        self.stop_btn.config(state=tk.NORMAL)

        self.worker = threading.Thread(target=self.run_bot, daemon=True)
        self.worker.start()

    def toggle_pause(self):
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_btn.config(text="Pause")
            self.log("Resumed.")
        else:
            self.pause_event.set()
            self.pause_btn.config(text="Resume")
            self.log("Paused. Current browser action will finish, then processing will wait.")

    def stop(self):
        self.stop_event.set()
        self.pause_event.clear()
        self.clear_checkpoint()
        self.log("Stop requested. The bot will stop after the current action. The next Start will begin from page 1.")

    def wait_if_paused(self):
        while self.pause_event.is_set() and not self.stop_event.is_set():
            time.sleep(0.3)

    def finish(self):
        self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.pause_btn.config(state=tk.DISABLED, text="Pause"))
        self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))

    def retry_action(self, action, description: str):
        attempts = MAX_RETRIES if self.retry_var.get() else 1
        last_exc = None
        for attempt in range(1, attempts + 1):
            try:
                return action()
            except Exception as exc:
                last_exc = exc
                if attempt < attempts:
                    self.log(f"{description} failed (attempt {attempt}/{attempts}). Retrying...")
                    time.sleep(1.2)
        raise last_exc

    def read_row_data(self, row, input_box):
        sku = row.locator(SKU_SELECTOR).first.inner_text(timeout=5000).strip().upper()
        current = clean_price(input_box.input_value())
        row_text = row.inner_text(timeout=5000)

        match = re.search(r"Lowest\s*Price[\s\S]{0,150}?AED\s*([0-9]+(?:\.[0-9]+)?)", row_text, re.I)
        lowest = clean_price(match.group(1)) if match else None

        if lowest is None:
            bolds = row.locator("b, strong")
            for b in range(bolds.count()):
                txt = bolds.nth(b).inner_text().strip()
                m = re.search(r"AED\s*([0-9]+(?:\.[0-9]+)?)", txt, re.I)
                if m:
                    lowest = clean_price(m.group(1))
                    break

        if not sku or current is None or lowest is None:
            raise RuntimeError("Could not read SKU, current price, or lowest price.")
        return sku, current, lowest

    def load_pricing_state(self):
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}
        except Exception:
            return {}

    def save_pricing_state(self, state):
        STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def load_checkpoint(self):
        try:
            return max(1, int(json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8")).get("page", 1)))
        except Exception:
            return 1

    def save_checkpoint(self, page_no):
        CHECKPOINT_FILE.write_text(json.dumps({"page": page_no, "saved_at": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=2), encoding="utf-8")

    def clear_checkpoint(self):
        try:
            CHECKPOINT_FILE.unlink(missing_ok=True)
        except OSError:
            pass

    def ensure_page_ready(self, page):
        try:
            page.wait_for_selector(INPUT_SELECTOR, timeout=15000)
            return page
        except Exception:
            self.log("Page became unavailable. Reopening Seller Hub...")
            try:
                page.reload(wait_until="domcontentloaded", timeout=60000)
            except Exception:
                page.goto(OFFERS_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector(INPUT_SELECTOR, timeout=30000)
            return page

    def process_cycle(self, page, writer, csv_file, cycle_no: int):
        cycle_updated = 0
        cycle_checked = 0
        pricing_state = self.load_pricing_state()

        # Every cycle starts from the first Seller Hub page. Pause/Resume works
        # inside the currently running cycle and does not restart the worker.
        resume_page = 1
        self.clear_checkpoint()

        page.goto(OFFERS_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)

        if "/login" in page.url.lower() or "signin" in page.url.lower():
            self.log("Seller Hub login is required. Please log in in the opened browser.")
            self.root.after(0, lambda: messagebox.showinfo(
                APP_TITLE,
                "Please log in to Seller Hub in the opened browser.\n\n"
                "After login, return to the application. It will continue automatically."
            ))
            login_deadline = time.time() + 300
            while time.time() < login_deadline and not self.stop_event.is_set():
                if "/login" not in page.url.lower() and "signin" not in page.url.lower():
                    break
                page.wait_for_timeout(1000)
            if "/login" in page.url.lower() or "signin" in page.url.lower():
                raise RuntimeError("Login was not completed within 5 minutes.")

        self.log("Starting from Seller Hub page 1.")

        for page_no in range(1, MAX_PAGES + 1):
            if self.stop_event.is_set():
                break
            self.wait_if_paused()

            self.stats["page"] = page_no
            self.update_status()
            self.log(f"Cycle {cycle_no}: processing page {page_no}...")

            page = self.ensure_page_ready(page)
            inputs = page.locator(INPUT_SELECTOR)
            count = inputs.count()

            if count == 0:
                raise RuntimeError("No offer price fields were found.")

            special_skus = load_special_skus()

            for index in range(count):
                if self.stop_event.is_set():
                    break
                self.wait_if_paused()

                input_box = inputs.nth(index)
                row = input_box.locator(
                    "xpath=ancestor::*[.//button[contains(@class,'offers-grid-btn-update')] "
                    "and .//*[contains(normalize-space(.),'Lowest Price')]][1]"
                )
                if row.count() == 0:
                    row = input_box.locator("xpath=ancestor::tr[1]")

                sku_for_log = f"row-{index+1}"

                try:
                    sku, current, lowest = self.read_row_data(row, input_box)
                    sku_for_log = sku
                    self.stats["current_sku"] = sku
                    is_special = sku in special_skus

                    previous = pricing_state.get(sku, {})
                    previous_bot_price = clean_price(previous.get("last_bot_price")) if previous else None

                    if is_special:
                        # On the first encounter, the displayed lowest price is treated as
                        # the competitor price, even when it equals our current price.
                        # This ensures a tied special SKU is undercut by AED 0.001.
                        if previous_bot_price is None:
                            target = lowest - Decimal("0.001")
                            action = "Special SKU first encounter - undercut lowest by 0.001"
                        # If our current price is exactly the last price set by the bot and
                        # Seller Hub still reports that same value as the lowest, do not
                        # lower it repeatedly on every cycle.
                        elif current == previous_bot_price and lowest == current:
                            target = current
                            action = "Special SKU already at last bot price - self-undercut protection"
                        elif lowest <= current:
                            target = lowest - Decimal("0.001")
                            action = "Special SKU competitor tied/lower - undercut by 0.001"
                        else:
                            target = lowest - Decimal("0.001")
                            action = "Special SKU Profit Recovery - remain 0.001 below lowest"
                    else:
                        target = lowest
                        action = "Match lowest"

                    target_text = format_price(target)
                    current_fmt = format_price(current)
                    lowest_fmt = format_price(lowest)

                    self.stats["checked"] += 1
                    cycle_checked += 1

                    if current == target:
                        self.stats["skipped"] += 1
                        self.log(f"{sku}: already correct at AED {target_text}.")
                        writer.writerow([
                            time.strftime("%Y-%m-%d %H:%M:%S"), cycle_no, page_no, sku,
                            current_fmt, lowest_fmt, target_text, action, "Skipped"
                        ])
                        self.update_status()
                        continue

                    if self.dry_run_var.get():
                        self.stats["skipped"] += 1
                        self.log(f"DRY RUN {sku}: would change AED {current_fmt} -> AED {target_text} ({action}).")
                        writer.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), cycle_no, page_no, sku, current_fmt, lowest_fmt, target_text, action, "Dry Run"])
                        self.update_status()
                        continue

                    def do_update():
                        input_box.scroll_into_view_if_needed()
                        input_box.fill(target_text)
                        page.wait_for_timeout(250)

                        update_btn = row.locator(UPDATE_SELECTOR).first
                        update_btn.wait_for(state="visible", timeout=5000)

                        for _ in range(30):
                            if not update_btn.is_disabled():
                                break
                            page.wait_for_timeout(150)

                        if update_btn.is_disabled():
                            raise RuntimeError("Update button did not become enabled.")

                        update_btn.click()
                        page.wait_for_timeout(ROW_WAIT_MS)

                    self.retry_action(do_update, f"Update for {sku}")

                    self.stats["updated"] += 1
                    cycle_updated += 1
                    pricing_state[sku] = {"last_bot_price": target_text, "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
                    self.save_pricing_state(pricing_state)
                    self.log(f"{sku}: AED {current_fmt} -> AED {target_text} ({action}).")
                    writer.writerow([
                        time.strftime("%Y-%m-%d %H:%M:%S"), cycle_no, page_no, sku,
                        current_fmt, lowest_fmt, target_text, action, "Updated"
                    ])

                except Exception as exc:
                    self.stats["errors"] += 1
                    self.log(f"{sku_for_log}: ERROR - {exc}")
                    writer.writerow([
                        time.strftime("%Y-%m-%d %H:%M:%S"), cycle_no, page_no, sku_for_log,
                        "", "", "", "", f"Error: {exc}"
                    ])
                    if not self.continue_errors_var.get():
                        raise

                self.update_status()
                csv_file.flush()

            if self.stop_event.is_set():
                break

            self.save_checkpoint(page_no + 1)
            next_btn = page.locator(NEXT_SELECTOR).first
            if next_btn.count() == 0 or not next_btn.is_visible() or next_btn.is_disabled():
                self.log(f"Cycle {cycle_no}: reached the last page.")
                self.clear_checkpoint()
                break

            next_btn.scroll_into_view_if_needed()
            next_btn.click()
            page.wait_for_timeout(PAGE_WAIT_MS)
            page.wait_for_selector(INPUT_SELECTOR, timeout=15000)

        return cycle_checked, cycle_updated

    def countdown_wait(self, seconds: int):
        remaining = int(seconds)
        while remaining > 0 and not self.stop_event.is_set():
            self.wait_if_paused()
            mins, secs = divmod(remaining, 60)
            self.root.after(0, lambda m=mins, s=secs: self.status_var.set(
                f"Waiting for next cycle: {m:02d}:{s:02d}"
            ))
            time.sleep(1)
            remaining -= 1

    def run_bot(self):
        LOG_DIR.mkdir(exist_ok=True)
        log_path = LOG_DIR / f"run_{time.strftime('%Y%m%d_%H%M%S')}.csv"
        csv_file = log_path.open("w", newline="", encoding="utf-8-sig")
        writer = csv.writer(csv_file)
        writer.writerow([
            "Time", "Cycle", "Page", "SKU", "Current Price",
            "Lowest Price", "Target Price", "Action", "Result"
        ])

        try:
            executable = detect_chrome()
            if not executable:
                raise RuntimeError("Google Chrome or Microsoft Edge was not found.")

            user_data_dir = str(BASE_DIR / "browser_profile")
            Path(user_data_dir).mkdir(exist_ok=True)
            self.log(f"Using dedicated automation profile: {user_data_dir}")
            self.log("On the first run, log in to Seller Hub in the opened browser. The login will be saved.")
            self.log(f"Log file: {log_path}")

            with sync_playwright() as p:
                try:
                    context = p.chromium.launch_persistent_context(
                        user_data_dir=user_data_dir,
                        executable_path=executable,
                        headless=False,
                        args=["--start-maximized", "--disable-features=LockProfileCookieDatabase"],
                        no_viewport=True,
                    )
                except Exception as exc:
                    raise RuntimeError(
                        "Could not open the dedicated automation browser profile. "
                        "Delete the 'browser_profile' folder beside PriceMatcher.exe and try again. "
                        f"Technical details: {exc}"
                    ) from exc

                page = context.pages[0] if context.pages else context.new_page()

                cycle_no = 0
                while not self.stop_event.is_set():
                    cycle_no += 1
                    self.stats.update({"cycle": cycle_no, "page": 0, "checked": 0, "updated": 0, "skipped": 0, "errors": 0, "current_sku": "", "last_action": "Starting cycle"})
                    self.update_status()

                    self.log("=" * 55)
                    self.log(f"Starting cycle #{cycle_no}")
                    self.log("=" * 55)

                    try:
                        cycle_checked, cycle_updated = self.process_cycle(page, writer, csv_file, cycle_no)
                        self.log(
                            f"Cycle #{cycle_no} finished. Checked: {cycle_checked}, Updated: {cycle_updated}."
                        )
                    except Exception as exc:
                        self.stats["errors"] += 1
                        self.update_status()
                        self.log(f"Cycle #{cycle_no} failed: {exc}")
                        if not self.continue_errors_var.get():
                            raise
                        cycle_updated = 0

                    csv_file.flush()

                    if self.stop_event.is_set() or not self.continuous_var.get():
                        break

                    base_minutes = max(float(self.interval_var.get()), 0.1)

                    if self.adaptive_var.get():
                        wait_minutes = 1 if cycle_updated > 0 else 3
                    else:
                        wait_minutes = base_minutes

                    self.log(f"Waiting {wait_minutes:g} minute(s) before restarting from page 1...")
                    self.countdown_wait(int(wait_minutes * 60))

                self.log(
                    f"Stopped. Last cycle: checked {self.stats['checked']}, updated {self.stats['updated']}, "
                    f"skipped {self.stats['skipped']}, errors {self.stats['errors']}."
                )
                context.close()

        except Exception as exc:
            self.stats["errors"] += 1
            self.update_status()
            self.log(f"FATAL ERROR: {exc}")
            self.root.after(0, lambda: messagebox.showerror(APP_TITLE, str(exc)))
        finally:
            csv_file.close()
            self.finish()

def main():
    root = tk.Tk()
    PriceMatcherApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()

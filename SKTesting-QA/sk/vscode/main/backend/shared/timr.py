from datetime import datetime
import pytz
import difflib
import random
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


# ================= TIMEZONE TO COUNTRY MAPPING =================
def countryNameFromTimezone(timezone: str) -> str:
    """Convert timezone string to country name"""
    timezone_to_country = {
        "Asia/Kabul": "Afghanistan",
        "Europe/Tirane": "Albania",
        "Africa/Algiers": "Algeria",
        "Europe/Andorra": "Andorra",
        "Africa/Luanda": "Angola",
        "America/Antigua": "Antigua and Barbuda",
        "America/Argentina/Buenos_Aires": "Argentina",
        "Asia/Yerevan": "Armenia",
        "Australia/Sydney": "Australia",
        "Europe/Vienna": "Austria",
        "Asia/Baku": "Azerbaijan",
        "America/Nassau": "Bahamas",
        "Asia/Bahrain": "Bahrain",
        "Asia/Dhaka": "Bangladesh",
        "America/Barbados": "Barbados",
        "Europe/Minsk": "Belarus",
        "Europe/Brussels": "Belgium",
        "America/Belize": "Belize",
        "Africa/Porto-Novo": "Benin",
        "Asia/Thimphu": "Bhutan",
        "America/La_Paz": "Bolivia",
        "Europe/Sarajevo": "Bosnia and Herzegovina",
        "Africa/Gaborone": "Botswana",
        "America/Sao_Paulo": "Brazil",
        "Asia/Brunei": "Brunei",
        "Europe/Sofia": "Bulgaria",
        "Africa/Ouagadougou": "Burkina Faso",
        "Africa/Bujumbura": "Burundi",
        "Atlantic/Cape_Verde": "Cabo Verde",
        "Asia/Phnom_Penh": "Cambodia",
        "Africa/Douala": "Cameroon",
        "America/Toronto": "Canada",
        "Africa/Bangui": "Central African Republic",
        "Africa/Ndjamena": "Chad",
        "America/Santiago": "Chile",
        "Asia/Shanghai": "China",
        "America/Bogota": "Colombia",
        "Indian/Comoro": "Comoros",
        "Africa/Brazzaville": "Congo (Congo-Brazzaville)",
        "America/Costa_Rica": "Costa Rica",
        "Europe/Zagreb": "Croatia",
        "America/Havana": "Cuba",
        "Asia/Nicosia": "Cyprus",
        "Europe/Prague": "Czech Republic",
        "Africa/Kinshasa": "Democratic Republic of the Congo",
        "Europe/Copenhagen": "Denmark",
        "Africa/Djibouti": "Djibouti",
        "America/Dominica": "Dominica",
        "America/Santo_Domingo": "Dominican Republic",
        "America/Guayaquil": "Ecuador",
        "Africa/Cairo": "Egypt",
        "America/El_Salvador": "El Salvador",
        "Africa/Malabo": "Equatorial Guinea",
        "Africa/Asmara": "Eritrea",
        "Europe/Tallinn": "Estonia",
        "Africa/Mbabane": "Eswatini",
        "Africa/Addis_Ababa": "Ethiopia",
        "Pacific/Fiji": "Fiji",
        "Europe/Helsinki": "Finland",
        "Europe/Paris": "France",
        "Africa/Libreville": "Gabon",
        "Africa/Banjul": "Gambia",
        "Asia/Tbilisi": "Georgia",
        "Europe/Berlin": "Germany",
        "Africa/Accra": "Ghana",
        "Europe/Athens": "Greece",
        "America/Grenada": "Grenada",
        "America/Guatemala": "Guatemala",
        "Africa/Conakry": "Guinea",
        "Africa/Bissau": "Guinea-Bissau",
        "America/Guyana": "Guyana",
        "America/Port-au-Prince": "Haiti",
        "Europe/Vatican": "Holy See",
        "America/Tegucigalpa": "Honduras",
        "Europe/Budapest": "Hungary",
        "Atlantic/Reykjavik": "Iceland",
        "Asia/Kolkata": "India",
        "Asia/Jakarta": "Indonesia",
        "Asia/Tehran": "Iran",
        "Asia/Baghdad": "Iraq",
        "Europe/Dublin": "Ireland",
        "Asia/Jerusalem": "Israel",
        "Europe/Rome": "Italy",
        "Africa/Abidjan": "Ivory Coast (Côte d'Ivoire)",
        "America/Jamaica": "Jamaica",
        "Asia/Tokyo": "Japan",
        "Asia/Amman": "Jordan",
        "Asia/Almaty": "Kazakhstan",
        "Africa/Nairobi": "Kenya",
        "Pacific/Tarawa": "Kiribati",
        "Asia/Kuwait": "Kuwait",
        "Asia/Bishkek": "Kyrgyzstan",
        "Asia/Vientiane": "Laos",
        "Europe/Riga": "Latvia",
        "Asia/Beirut": "Lebanon",
        "Africa/Maseru": "Lesotho",
        "Africa/Monrovia": "Liberia",
        "Africa/Tripoli": "Libya",
        "Europe/Vaduz": "Liechtenstein",
        "Europe/Vilnius": "Lithuania",
        "Europe/Luxembourg": "Luxembourg",
        "Indian/Antananarivo": "Madagascar",
        "Africa/Blantyre": "Malawi",
        "Asia/Kuala_Lumpur": "Malaysia",
        "Indian/Maldives": "Maldives",
        "Africa/Bamako": "Mali",
        "Europe/Malta": "Malta",
        "Pacific/Majuro": "Marshall Islands",
        "Africa/Nouakchott": "Mauritania",
        "Indian/Mauritius": "Mauritius",
        "America/Mexico_City": "Mexico",
        "Pacific/Pohnpei": "Micronesia (Federated States of)",
        "Europe/Chisinau": "Moldova",
        "Europe/Monaco": "Monaco",
        "Asia/Ulaanbaatar": "Mongolia",
        "Europe/Podgorica": "Montenegro",
        "Africa/Casablanca": "Morocco",
        "Africa/Maputo": "Mozambique",
        "Asia/Yangon": "Myanmar",
        "Africa/Windhoek": "Namibia",
        "Pacific/Nauru": "Nauru",
        "Asia/Kathmandu": "Nepal",
        "Europe/Amsterdam": "Netherlands",
        "Pacific/Auckland": "New Zealand",
        "America/Managua": "Nicaragua",
        "Africa/Niamey": "Niger",
        "Africa/Lagos": "Nigeria",
        "Asia/Pyongyang": "North Korea",
        "Europe/Skopje": "North Macedonia",
        "Europe/Oslo": "Norway",
        "Asia/Muscat": "Oman",
        "Asia/Karachi": "Pakistan",
        "Pacific/Palau": "Palau",
        "Asia/Gaza": "Palestine",
        "America/Panama": "Panama",
        "Pacific/Port_Moresby": "Papua New Guinea",
        "America/Asuncion": "Paraguay",
        "America/Lima": "Peru",
        "Asia/Manila": "Philippines",
        "Europe/Warsaw": "Poland",
        "Europe/Lisbon": "Portugal",
        "Asia/Qatar": "Qatar",
        "Europe/Bucharest": "Romania",
        "Europe/Moscow": "Russia",
        "Africa/Kigali": "Rwanda",
        "America/St_Kitts": "Saint Kitts and Nevis",
        "America/St_Lucia": "Saint Lucia",
        "Africa/Sao_Tome": "Saint Thomas and Prince (São Tomé and Príncipe)",
        "America/St_Vincent": "Saint Vincent and the Grenadines",
        "Pacific/Apia": "Samoa",
        "Europe/San_Marino": "San Marino",
        "Asia/Riyadh": "Saudi Arabia",
        "Africa/Dakar": "Senegal",
        "Europe/Belgrade": "Serbia",
        "Indian/Mahe": "Seychelles",
        "Africa/Freetown": "Sierra Leone",
        "Asia/Singapore": "Singapore",
        "Europe/Bratislava": "Slovakia",
        "Europe/Ljubljana": "Slovenia",
        "Pacific/Guadalcanal": "Solomon Islands",
        "Africa/Mogadishu": "Somalia",
        "Africa/Johannesburg": "South Africa",
        "Asia/Seoul": "South Korea",
        "Africa/Juba": "South Sudan",
        "Europe/Madrid": "Spain",
        "Asia/Colombo": "Sri Lanka",
        "Africa/Khartoum": "Sudan",
        "America/Paramaribo": "Suriname",
        "Europe/Stockholm": "Sweden",
        "Europe/Zurich": "Switzerland",
        "Asia/Damascus": "Syria",
        "Asia/Taipei": "Taiwan",
        "Asia/Dushanbe": "Tajikistan",
        "Africa/Dar_es_Salaam": "Tanzania",
        "Asia/Bangkok": "Thailand",
        "Asia/Dili": "Timor-Leste",
        "Africa/Lome": "Togo",
        "Pacific/Tongatapu": "Tonga",
        "America/Port_of_Spain": "Trinidad and Tobago",
        "Africa/Tunis": "Tunisia",
        "Europe/Istanbul": "Turkey",
        "Asia/Ashgabat": "Turkmenistan",
        "Pacific/Funafuti": "Tuvalu",
        "Africa/Kampala": "Uganda",
        "Europe/Kyiv": "Ukraine",
        "Asia/Dubai": "United Arab Emirates",
        "Europe/London": "United Kingdom",
        "America/New_York": "United States of America",
        "America/Montevideo": "Uruguay",
        "Asia/Tashkent": "Uzbekistan",
        "Pacific/Efate": "Vanuatu",
        "America/Caracas": "Venezuela",
        "Asia/Ho_Chi_Minh": "Vietnam",
        "Asia/Aden": "Yemen",
        "Africa/Lusaka": "Zambia",
        "Africa/Harare": "Zimbabwe",
    }

    return timezone_to_country.get(timezone, "Unknown")


# ================= FORMAT UTC OFFSET =================
def format_offset(offset_hours):
    """Format UTC offset as +HH:MM or -HH:MM"""
    offset_hours = float(offset_hours)
    sign = "+" if offset_hours >= 0 else "-"
    abs_hours = abs(offset_hours)
    h = int(abs_hours)
    m = int(round((abs_hours - h) * 60))
    return f"{sign}{h}" if m == 0 else f"{sign}{h}:{m:02d}"


# ================= SAFE CLICK =================
def safe_click(locator, timeout=15000):
    """Safely click an element with visibility and scroll checks"""
    try:
        locator.wait_for(state="attached", timeout=timeout)
        locator.wait_for(state="visible", timeout=timeout)
        locator.scroll_into_view_if_needed()
        locator.page.wait_for_load_state("networkidle")
        try:
            locator.click(timeout=10000)
        except:
            locator.click(force=True)
    except Exception as e:
        print(f"[ERROR] Safe click failed: {e}")
        raise


# ================= DROPDOWN FILTER + SELECT =================
def type_in_dropdown_filter_dynamic(page, filter_text):
    """Type in dropdown filter and select matching option"""
    try:
        filter_input = page.locator("input.p-dropdown-filter").last
        filter_input.wait_for(state="visible", timeout=5000)
        filter_input.click()
        filter_input.clear()

        # Human typing simulation
        for char in filter_text:
            filter_input.type(char, delay=random.randint(60, 140))

        page.wait_for_timeout(600)

        aria_owns = filter_input.get_attribute("aria-owns")
        options_locator = page.locator(f"#{aria_owns} li.p-dropdown-item")
        options_locator.first.wait_for(state="visible", timeout=5000)

        all_options = options_locator.all_inner_texts()
        print(f"[DEBUG] Available options: {all_options[:5]}...")  # Show first 5

        # Exact match
        if filter_text in all_options:
            matched = filter_text
        else:
            matches = difflib.get_close_matches(filter_text, all_options, n=1, cutoff=0.4)
            if matches:
                matched = matches[0]
                print(f"[WARN] Fuzzy match: '{filter_text}' -> '{matched}'")
            else:
                print(f"[ERROR] No match found for: '{filter_text}'")
                print(f"[DEBUG] All options: {all_options}")
                return False

        option = page.locator(f"#{aria_owns} li.p-dropdown-item:has-text('{matched}')")
        safe_click(option)
        print(f"[OK] Selected: {matched}")
        return True

    except Exception as e:
        print(f"[ERROR] Dropdown selection failed: {e}")
        return False


# ================= SETTINGS PAGE LOGIC =================
def settings(page, timezone_name, country_name):
    """Update company settings with timezone and country"""
    try:
        print(f"\n[SETTINGS] Updating Country: {country_name} | Timezone: {timezone_name}")

        # Navigate to settings
        logo_btn = page.locator("button:has(img[src*='white_logo.png'])")
        safe_click(logo_btn)
        page.wait_for_timeout(1000)

        settings_link = page.locator("#audit-settings-link")
        safe_click(settings_link)
        page.wait_for_timeout(1000)

        company_link = page.locator("a[href='/home/company']").first
        safe_click(company_link)
        page.wait_for_timeout(1500)

        #    STEP 1: SELECT COUNTRY FIRST
        print("\n[STEP 1] Selecting Country...")
        country_dropdown = page.locator(
            "div:has(label:has-text('Country')) p-dropdown, "
            "div:has(span:has-text('Country')) p-dropdown"
        ).first

        if not country_dropdown.is_visible():
            print("[ERROR] Country dropdown not found")
            return False

        safe_click(country_dropdown)
        page.wait_for_timeout(500)

        if not type_in_dropdown_filter_dynamic(page, country_name):
            print(f"[ERROR] Failed to select country: {country_name}")
            return False

        page.wait_for_timeout(1500)  # Wait for form to update

        #    STEP 2: SELECT TIMEZONE (after country is set)
        print("\n[STEP 2] Selecting Timezone...")
        timezone_dropdown = page.locator(
            "div:has(label:has-text('Time Zone')) p-dropdown, "
            "div:has(span:has-text('Time Zone')) p-dropdown"
        ).first

        if not timezone_dropdown.is_visible():
            print("[ERROR] Timezone dropdown not found")
            return False

        safe_click(timezone_dropdown)
        page.wait_for_timeout(500)

        if not type_in_dropdown_filter_dynamic(page, timezone_name):
            print(f"[ERROR] Failed to select timezone: {timezone_name}")
            return False

        page.wait_for_timeout(1000)

        #    STEP 3: SAVE CHANGES
        print("\n[STEP 3] Saving changes...")
        update_btn = page.locator("button:has-text('Update')")

        if not update_btn.is_visible():
            print("[ERROR] Update button not found")
            return False

        safe_click(update_btn)
        page.wait_for_timeout(2000)

        print("[OK]    Settings updated successfully!")
        return True

    except Exception as e:
        print(f"[ERROR] Settings update failed: {e}")
        return False


# ================= DYNAMIC TIMEZONE SELECTION =================
def timezone(page):
    """
    Find timezone nearest to 00:00:00 (midnight) and auto-select in settings
    """

    # 👉 Full timezone list
    my_timezones = [
        # ================= AFRICA =================
        "Africa/Abidjan", "Africa/Accra", "Africa/Addis_Ababa", "Africa/Algiers",
        "Africa/Asmara", "Africa/Bamako", "Africa/Bangui", "Africa/Banjul",
        "Africa/Bissau", "Africa/Blantyre", "Africa/Brazzaville", "Africa/Bujumbura",
        "Africa/Cairo", "Africa/Casablanca", "Africa/Ceuta", "Africa/Conakry",
        "Africa/Dakar", "Africa/Dar_es_Salaam", "Africa/Djibouti", "Africa/Douala",
        "Africa/El_Aaiun", "Africa/Freetown", "Africa/Gaborone", "Africa/Harare",
        "Africa/Johannesburg", "Africa/Juba", "Africa/Kampala", "Africa/Khartoum",
        "Africa/Kigali", "Africa/Kinshasa", "Africa/Libreville", "Africa/Lome",
        "Africa/Luanda", "Africa/Lubumbashi", "Africa/Lusaka", "Africa/Malabo",
        "Africa/Maputo", "Africa/Maseru", "Africa/Mbabane", "Africa/Mogadishu",
        "Africa/Monrovia", "Africa/Nairobi", "Africa/Ndjamena", "Africa/Niamey",
        "Africa/Nouakchott", "Africa/Ouagadougou", "Africa/Porto-Novo",
        "Africa/Sao_Tome", "Africa/Tripoli", "Africa/Tunis", "Africa/Windhoek",

        # ================= AMERICA =================
        "America/Adak", "America/Anchorage", "America/Anguilla", "America/Antigua",
        "America/Araguaina", "America/Argentina/Buenos_Aires",
        "America/Argentina/Catamarca", "America/Argentina/Cordoba",
        "America/Argentina/Jujuy", "America/Argentina/La_Rioja",
        "America/Argentina/Mendoza", "America/Argentina/Rio_Gallegos",
        "America/Argentina/Salta", "America/Argentina/San_Juan",
        "America/Argentina/San_Luis", "America/Argentina/Tucuman",
        "America/Argentina/Ushuaia", "America/Aruba", "America/Asuncion",
        "America/Atikokan", "America/Bahia", "America/Bahia_Banderas",
        "America/Barbados", "America/Belem", "America/Belize",
        "America/Blanc-Sablon", "America/Boa_Vista", "America/Boise",
        "America/Cambridge_Bay", "America/Campo_Grande", "America/Cancun",
        "America/Caracas", "America/Cayenne", "America/Cayman",
        "America/Chicago", "America/Chihuahua", "America/Costa_Rica",
        "America/Creston", "America/Cuiaba", "America/Curacao",
        "America/Danmarkshavn", "America/Dawson", "America/Dawson_Creek",
        "America/Denver", "America/Detroit", "America/Dominica",
        "America/Edmonton", "America/Eirunepe", "America/El_Salvador",
        "America/Fortaleza", "America/Glace_Bay", "America/Grand_Turk",
        "America/Grenada", "America/Guadeloupe", "America/Guatemala",
        "America/Guayaquil", "America/Guyana", "America/Halifax",
        "America/Havana", "America/Hermosillo",
        "America/Indiana/Indianapolis", "America/Indiana/Knox",
        "America/Indiana/Marengo", "America/Indiana/Petersburg",
        "America/Indiana/Tell_City", "America/Indiana/Vevay",
        "America/Indiana/Vincennes", "America/Indiana/Winamac",
        "America/Inuvik", "America/Iqaluit", "America/Jamaica",
        "America/Juneau", "America/Kentucky/Louisville",
        "America/Kentucky/Monticello", "America/La_Paz", "America/Lima",
        "America/Los_Angeles", "America/Lower_Princes",
        "America/Maceio", "America/Managua", "America/Manaus",
        "America/Martinique", "America/Matamoros", "America/Mazatlan",
        "America/Menominee", "America/Merida", "America/Metlakatla",
        "America/Mexico_City", "America/Miquelon", "America/Moncton",
        "America/Monterrey", "America/Montevideo", "America/Montserrat",
        "America/Nassau", "America/New_York", "America/Nome",
        "America/Noronha", "America/North_Dakota/Beulah",
        "America/North_Dakota/Center", "America/North_Dakota/New_Salem",
        "America/Ojinaga", "America/Panama", "America/Pangnirtung",
        "America/Paramaribo", "America/Phoenix", "America/Port-au-Prince",
        "America/Port_of_Spain", "America/Porto_Velho",
        "America/Puerto_Rico", "America/Punta_Arenas",
        "America/Rainy_River", "America/Rankin_Inlet", "America/Recife",
        "America/Regina", "America/Resolute", "America/Rio_Branco",
        "America/Santarem", "America/Santiago", "America/Santo_Domingo",
        "America/Sao_Paulo", "America/Scoresbysund", "America/Sitka",
        "America/St_Barthelemy", "America/St_Johns", "America/St_Kitts",
        "America/St_Lucia", "America/St_Thomas", "America/St_Vincent",
        "America/Swift_Current", "America/Tegucigalpa", "America/Thule",
        "America/Thunder_Bay", "America/Tijuana", "America/Toronto",
        "America/Tortola", "America/Vancouver", "America/Whitehorse",
        "America/Winnipeg", "America/Yakutat", "America/Yellowknife",

        # ================= ASIA =================
        "Asia/Aden", "Asia/Almaty", "Asia/Amman", "Asia/Anadyr",
        "Asia/Aqtau", "Asia/Aqtobe", "Asia/Ashgabat", "Asia/Atyrau",
        "Asia/Baghdad", "Asia/Bahrain", "Asia/Baku", "Asia/Bangkok",
        "Asia/Barnaul", "Asia/Beirut", "Asia/Bishkek", "Asia/Brunei",
        "Asia/Chita", "Asia/Choibalsan", "Asia/Colombo", "Asia/Damascus",
        "Asia/Dhaka", "Asia/Dili", "Asia/Dubai", "Asia/Dushanbe",
        "Asia/Famagusta", "Asia/Gaza", "Asia/Hebron",
        "Asia/Ho_Chi_Minh", "Asia/Hong_Kong", "Asia/Hovd",
        "Asia/Irkutsk", "Asia/Jakarta", "Asia/Jayapura",
        "Asia/Jerusalem", "Asia/Kabul", "Asia/Kamchatka",
        "Asia/Karachi", "Asia/Kathmandu", "Asia/Khandyga",
        "Asia/Kolkata", "Asia/Krasnoyarsk", "Asia/Kuala_Lumpur",
        "Asia/Kuching", "Asia/Kuwait", "Asia/Macau", "Asia/Magadan",
        "Asia/Makassar", "Asia/Manila", "Asia/Muscat",
        "Asia/Nicosia", "Asia/Novokuznetsk", "Asia/Novosibirsk",
        "Asia/Omsk", "Asia/Oral", "Asia/Phnom_Penh",
        "Asia/Pontianak", "Asia/Pyongyang", "Asia/Qatar",
        "Asia/Qostanay", "Asia/Qyzylorda", "Asia/Riyadh",
        "Asia/Sakhalin", "Asia/Samarkand", "Asia/Seoul",
        "Asia/Shanghai", "Asia/Singapore", "Asia/Srednekolymsk",
        "Asia/Taipei", "Asia/Tashkent", "Asia/Tbilisi",
        "Asia/Tehran", "Asia/Thimphu", "Asia/Tokyo",
        "Asia/Tomsk", "Asia/Ulaanbaatar", "Asia/Urumqi",
        "Asia/Ust-Nera", "Asia/Vientiane", "Asia/Vladivostok",
        "Asia/Yakutsk", "Asia/Yekaterinburg", "Asia/Yerevan",

        # ================= EUROPE =================
        "Europe/Amsterdam", "Europe/Andorra", "Europe/Astrakhan",
        "Europe/Athens", "Europe/Belgrade", "Europe/Berlin",
        "Europe/Bratislava", "Europe/Brussels", "Europe/Bucharest",
        "Europe/Budapest", "Europe/Chisinau", "Europe/Copenhagen",
        "Europe/Dublin", "Europe/Gibraltar", "Europe/Guernsey",
        "Europe/Helsinki", "Europe/Isle_of_Man", "Europe/Istanbul",
        "Europe/Jersey", "Europe/Kaliningrad", "Europe/Kyiv",
        "Europe/Kirov", "Europe/Lisbon", "Europe/Ljubljana",
        "Europe/London", "Europe/Luxembourg", "Europe/Madrid",
        "Europe/Malta", "Europe/Mariehamn", "Europe/Minsk",
        "Europe/Monaco", "Europe/Moscow", "Europe/Oslo",
        "Europe/Paris", "Europe/Podgorica", "Europe/Prague",
        "Europe/Riga", "Europe/Rome", "Europe/Samara",
        "Europe/San_Marino", "Europe/Sarajevo", "Europe/Saratov",
        "Europe/Simferopol", "Europe/Skopje", "Europe/Sofia",
        "Europe/Stockholm", "Europe/Tallinn", "Europe/Tirane",
        "Europe/Ulyanovsk", "Europe/Uzhgorod", "Europe/Vaduz",
        "Europe/Vatican", "Europe/Vienna", "Europe/Vilnius",
        "Europe/Volgograd", "Europe/Warsaw", "Europe/Zagreb",
        "Europe/Zaporozhye", "Europe/Zurich",

        # ================= AUSTRALIA =================
        "Australia/Adelaide", "Australia/Brisbane", "Australia/Broken_Hill",
        "Australia/Currie", "Australia/Darwin", "Australia/Eucla",
        "Australia/Hobart", "Australia/Lindeman", "Australia/Lord_Howe",
        "Australia/Melbourne", "Australia/Perth", "Australia/Sydney"
    ]

    print("\n" + "="*70)
    print("🔍 TIMEZONE DETECTION - Finding nearest to 00:00:00 (Midnight)")
    print("="*70)

    utc_now = datetime.now(pytz.utc)
    target_seconds = 0  # 🎯 Midnight 00:00:00

    closest_zone = None
    smallest_diff = float("inf")

    # Find timezone closest to midnight
    for tz_name in my_timezones:
        try:
            tz = pytz.timezone(tz_name)
            local_time = utc_now.astimezone(tz)

            local_seconds = (
                local_time.hour * 3600 +
                local_time.minute * 60 +
                local_time.second
            )

            # 🔥 Circular 24-hour difference
            diff = min(
                abs(local_seconds - target_seconds),
                86400 - abs(local_seconds - target_seconds)
            )

            if diff < smallest_diff:
                smallest_diff = diff
                closest_zone = {
                    "timezone": tz_name,
                    "date_str": local_time.strftime("%Y-%m-%d"),
                    "time_str": local_time.strftime("%H:%M:%S"),
                    "offset": local_time.utcoffset().total_seconds() / 3600
                }

        except Exception as e:
            print(f"[SKIP] {tz_name}: {e}")
            continue

    if not closest_zone:
        print("[ERROR]  No valid timezone found")
        return False

    # Get country for this timezone
    country_name = countryNameFromTimezone(closest_zone["timezone"])

    print("\n" + "="*70)
    print("   RESULTS:")
    print("="*70)
    print(f"Selected Timezone : {closest_zone['timezone']}")
    print(f"Country           : {country_name}")
    print(f"Local Date        : {closest_zone['date_str']}")
    print(f"Local Time        : {closest_zone['time_str']}")
    print(f"UTC Offset        : {format_offset(closest_zone['offset'])}")
    print(f"Difference        : {smallest_diff} seconds from midnight")
    print("="*70 + "\n")

    # 🔥 Call settings with both timezone and country
    success = settings(page, closest_zone["timezone"], country_name)

    if success:
        print("\n[SUCCESS]    Automation completed successfully!")
    else:
        print("\n[FAILED]  Automation failed during settings update")

    return success


# ================= MAIN EXECUTION =================
if __name__ == "__main__":
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # Navigate to your application
        page.goto("http://localhost:3000")  # Change to your app URL
        page.wait_for_timeout(2000)

        # Run timezone automation
        try:
            timezone(page)
        except Exception as e:
            print(f"[CRITICAL ERROR] {e}")
        finally:
            browser.close()
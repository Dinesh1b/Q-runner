import time



# --------------------------------------------------------------
# GLOBAL SPEED CONTROL
# --------------------------------------------------------------
SLEEP_TIME = 1

def Ad_hoc_Audit(page, Config):


    # ---------------------------
    # Select Item Group Dropdown
    # ---------------------------
# --------------------------------------------------------------
# SELECT ITEM GROUP
# --------------------------------------------------------------
    def select_item_group(page, Group_Name):








        dropdown = page.locator("#itemgroup")
        dropdown.locator('[aria-label="dropdown trigger"]').click()
        # The panel is appended to body
        panel = page.locator(
            "div.new-prime-panel.p-dropdown-panel"
        ).last

        panel.wait_for(
            state="visible",
            timeout=30000
        )

        # Search Item Group
        search = panel.locator(
            "input.p-dropdown-filter"
        )

        search.wait_for(
            state="visible",
            timeout=30000
        )

        search.fill("")
        search.fill(Group_Name)

        page.wait_for_timeout(500)

        # Select exact matching option
        option = panel.locator(
            "li.p-dropdown-item"
        ).filter(
            has=page.locator(
                "span.gsd-name",
                has_text=Group_Name
            )
        ).first

        option.wait_for(
            state="visible",
            timeout=30000
        )

        option.click()

        print(
            f"   Item Group selected: {Group_Name}"
        )




    # --------------------------------------------------------------
    # SELECT BRANCH (PrimeNG p-dropdown via XPath)
    # --------------------------------------------------------------
    def select_branch(page, branch_text: str):
        dropdown = page.locator(
            'xpath=/html/body/app-root/app-layout/div/app-header/div[1]/div[2]/div[2]//p-dropdown'
        )
        dropdown.wait_for(state="visible", timeout=30000)
        dropdown.locator(".p-dropdown-label").click()

        panel = page.locator(".p-dropdown-panel").last
        panel.wait_for(state="visible", timeout=30000)

        search = panel.locator("input.p-dropdown-filter")
        if search.count() > 0:
            search.fill("")
            search.fill(branch_text)
            page.wait_for_timeout(300)

        option = panel.locator("li.p-dropdown-item", has_text=branch_text)
        if option.count() == 0:
            raise Exception(f" Branch not found: {branch_text}")

        option.first.click()
        panel.wait_for(state="hidden", timeout=30000)

        dropdown.locator(
            ".p-dropdown-label", has_text=branch_text
        ).wait_for(state="visible", timeout=30000)




    # --------------------------------------------------------------
    # CREATE AUDIT NAME
    # --------------------------------------------------------------
    def create_name(page, Config):
        ap_audit_name = Config.ap_audit_name
        input_selector = page.get_by_placeholder("Enter audit name")
        input_selector.fill(ap_audit_name)
        submit_button = page.get_by_role("button", name="Create Audit", exact=True)
        submit_button.click()


        # --------------------------------------------------------------
    # SELECT MANUAL TAB
    # --------------------------------------------------------------
    def select_manual_tab(page):
        tab = page.get_by_role("tab", name="Manual")
        tab.wait_for(state="visible", timeout=30000)
        tab.click()
        # confirm it became the active tab
        page.locator("button.create-type-tab.is-active", has_text="Manual").wait_for(
            state="visible", timeout=30000
        )
    # --------------------------------------------------------------
    # MAIN FLOW
    # --------------------------------------------------------------
    def create_Ad_hoc_Audit(page):
        page.wait_for_selector("a[href='/home/audit']", state="visible")
        page.click("a[href='/home/audit']")
        time.sleep(SLEEP_TIME)

        # Branch selection before creating audit to avoid branch-related issues
        select_branch(page, Config.Branch)
        print(f"   Branch selected: {Config.Branch}")
        time.sleep(SLEEP_TIME)
        page.locator("button.createAuditBtn", has_text="Create Audit").click()
        
        time.sleep(SLEEP_TIME)
        select_manual_tab(page)
        time.sleep(SLEEP_TIME)

                # --------------------------------------------------------------
        # SELECT AUDIT TYPE
        # --------------------------------------------------------------
        audit_type = str(Config.Audit_Type).strip()

        page.get_by_role(
            "radio",
            name=audit_type
        ).click()

        print(f"   Selected Audit Type: {audit_type}")

        time.sleep(SLEEP_TIME)


        # --------------------------------------------------------------
        # CLICK CONTINUE
        # --------------------------------------------------------------
        page.get_by_role(
            "button",
            name="Continue"
        ).click()

        print("   Continue clicked")

        time.sleep(SLEEP_TIME)


        # --------------------------------------------------------------
        # COMPLETE AUDIT
        # Select Static or Dynamic
        # --------------------------------------------------------------
        if audit_type == "Complete Audit":

            SD_audit_type = str(
                getattr(Config, "SD_audit_type", "Static")
            ).strip().lower()

            if SD_audit_type == "static":

                page.locator(
                    "p-radiobutton[value='Static']"
                ).click()

                print("   Selected Static audit type")

            elif SD_audit_type == "dynamic":

                page.locator(
                    "p-radiobutton[value='Dynamic']"
                ).click()

                print("   Selected Dynamic audit type")

            else:
                raise ValueError(
                    f"Invalid SD_audit_type: {SD_audit_type}. "
                    "Use Static or Dynamic."
                )


        # --------------------------------------------------------------
        # PARTIAL AUDIT
        # Static by default
        # Do NOT click Static/Dynamic
        # --------------------------------------------------------------
        elif audit_type == "Partial Audit":

            print(
                "   Partial Audit selected - "
                "Static by default"
            )


        # --------------------------------------------------------------
        # INVESTIGATION AUDIT
        # Static by default
        # Do NOT click Static/Dynamic
        # --------------------------------------------------------------
        elif audit_type == "Investigation Audit":

            print(
                "   Investigation Audit selected - "
                "Static by default"
            )


        else:
            raise ValueError(
                f"Unsupported Audit Type: {audit_type}"
            )

        time.sleep(SLEEP_TIME)
        select_item_group(page, Group_Name=Config.Group_Name)
        
        create_name(page, Config)

        
        time.sleep(SLEEP_TIME)

    # --------------------------------------------------------------
    # ENTRY POINT
    # --------------------------------------------------------------
    create_Ad_hoc_Audit(page)

from pygame_menu.locals import ALIGN_LEFT

from src.managers.user_manager import REGIONS
from src.ui import ui_style as ui
from src.ui.menu.common import _batched, _first_arg


class ProfileMixin:
    """Player profile: first-run setup and editing the username and region."""

    # ================================================================ profile
    def _open_user_edit(self):
        self.sound_manager.play("menu_select")
        self.user_setup_username = self.user_manager.get_username() or ""
        region = self.user_manager.get_region()
        self.user_setup_region_index = REGIONS.index(region) if region in REGIONS else 0
        self.username_error = None
        self._create_user_edit_content()
        self._change_menu(self.user_edit_menu)
        self._focus_input(self.user_edit_menu, "edit_username_input")

    def needs_user_setup(self) -> bool:
        return not self.user_manager.is_setup_completed()

    def show_user_setup(self):
        self.user_setup_active = True
        self.user_setup_username = ""
        self.user_setup_region_index = 0
        self.username_error = None
        self._create_user_setup_content()
        self._change_menu(self.user_setup_menu)
        self._focus_input(self.user_setup_menu, "username_input")

    def _focus_input(self, menu, input_id):
        try:
            menu.select_widget(input_id)
        except Exception as e:
            print(f"Error focusing text input: {e}")

    def _on_username_change(self, value):
        self.user_setup_username = value

    def _on_region_change(self, selected, index):
        self.sound_manager.play("menu_select")
        self.user_setup_region_index = index

    _on_edit_username_change = _on_username_change
    _on_edit_region_change = _on_region_change

    def _confirm_user_setup(self):
        username = self.user_setup_username.strip()
        if not username:
            self.username_error = "Enter a username to continue."
            self._create_user_setup_content()
            self._focus_input(self.user_setup_menu, "username_input")
            return
        if self.supabase_manager and self.supabase_manager.is_configured():
            if self.supabase_manager.is_username_taken(username):
                self.username_error = "That username is taken. Try another one."
                self.sound_manager.play("menu_select")
                self._create_user_setup_content()
                self._focus_input(self.user_setup_menu, "username_input")
                return

        self.username_error = None
        region = REGIONS[self.user_setup_region_index]
        self.user_manager.complete_setup(username, region)
        self.sound_manager.play("menu_apply")
        self.user_setup_active = False

        if self.supabase_manager and self.supabase_manager.is_configured():
            self.supabase_manager.set_user_hash(
                self.user_manager.get_user_id(),
                self.user_manager.user_data.get("created_at", "")
            )
            if self.personal_best_manager:
                self.personal_best_manager.sync_all_to_cloud()

        self.refresh_main_menu_buttons()
        self._build_modes_page(self.difficulty_menu)
        self._change_menu(self.difficulty_menu)

    def _save_user_edit(self):
        username = self.user_setup_username.strip()
        if not username:
            self.username_error = "Enter a username to continue."
            self._create_user_edit_content()
            self._focus_input(self.user_edit_menu, "edit_username_input")
            return
        if self.supabase_manager and self.supabase_manager.is_configured():
            current_user_hash = self.supabase_manager.get_user_hash()
            if self.supabase_manager.is_username_taken(username, exclude_user_hash=current_user_hash):
                self.username_error = "That username is taken. Try another one."
                self.sound_manager.play("menu_select")
                self._create_user_edit_content()
                self._focus_input(self.user_edit_menu, "edit_username_input")
                return

        self.username_error = None
        region = REGIONS[self.user_setup_region_index]
        if self.supabase_manager and self.supabase_manager.is_configured():
            # Keep the same user hash, only rename existing records
            self.supabase_manager.update_user_profile(username, region)
        self.user_manager.update_user(username, region)
        self.sound_manager.play("menu_apply")
        self.refresh_main_menu_buttons()
        self._open_personal_best()

    def _back_from_user_setup(self):
        self.user_setup_active = False
        self._back_to_main()

    # ---------------------------------------------------------------- profile forms
    @_batched(_first_arg)
    def _profile_form(self, menu, title, intro, input_id, onchange, primary, secondary):
        menu.clear()
        width = self.pages[menu]["width"]
        self._surface(menu, self._text_surface(title, ui.display_font(ui.SIZE_H1), ui.TEXT, width))
        self._spacer(menu, 6)
        self._text(menu, intro, ui.body_font(), ui.MUTED)
        self._spacer(menu, 32)

        label_f = ui.body_font(ui.SIZE_SMALL, bold=True)
        self._text(menu, "Username", label_f, ui.TEXT)
        self._spacer(menu, 8)
        field_h = ui.px(60)
        # Text inputs only fit in vertical frames; center it with a top margin
        field = menu.add.frame_v(width, field_h, padding=0, background_color=ui.SURFACE_2,
                                 border_width=max(1, ui.px(1.5)), border_color=ui.LINE)
        field._pack_margin_warning = False
        text_input = menu.add.text_input(
            "", default=self.user_setup_username, maxchar=20, textinput_id=input_id, onchange=onchange,
            font_name=ui.FONT_BODY, font_size=ui.fs(ui.SIZE_BODY), font_color=ui.TEXT,
            input_underline="", copy_paste_enable=True, password=False)
        text_input._ui_ring_frame = field
        field.pack(menu.add.vertical_margin(max(0, (field_h - text_input.get_height()) // 2)))
        field.pack(text_input, align=ALIGN_LEFT, margin=(ui.px(16), 0))
        self._spacer(menu, 8)
        if self.username_error:
            self._text(menu, self.username_error, ui.body_font(ui.SIZE_SMALL), ui.DANGER)
        else:
            self._text(menu, "Up to 20 characters. Shown on leaderboards.", ui.body_font(ui.SIZE_SMALL), ui.MUTED)
        self._spacer(menu, 24)

        self._text(menu, "Region", label_f, ui.TEXT)
        self._spacer(menu, 8)
        region_items = [(region, i) for i, region in enumerate(REGIONS)]
        self._dropselect(menu, region_items, self.user_setup_region_index, self._on_region_change, width,
                         visible=5, widget_id=f"{input_id}_region")
        self._spacer(menu, 40)

        gap = ui.px(16)
        bw = (width - gap) // 2
        frame = menu.add.frame_h(width, ui.px(60), padding=0)
        frame._pack_margin_warning = False
        frame.pack(self._button(menu, secondary[0], secondary[1], w=bw, h=ui.px(60)))
        frame.pack(menu.add.horizontal_margin(gap))
        frame.pack(self._button(menu, primary[0], primary[1], w=bw, h=ui.px(60), variant="primary"))
        return text_input

    def _create_user_setup_content(self):
        self.username_input = self._profile_form(
            self.user_setup_menu, "Create your profile",
            "Pick a name and region for the global leaderboards. You can change them later.",
            "username_input", self._on_username_change,
            ("Continue", self._confirm_user_setup), ("Back", self._back_from_user_setup))

    def _create_user_edit_content(self):
        self.edit_username_input = self._profile_form(
            self.user_edit_menu, "Edit profile", "Your new name also updates the records you already posted.",
            "edit_username_input", self._on_edit_username_change,
            ("Save", self._save_user_edit), ("Cancel", self._back_to_statistics))

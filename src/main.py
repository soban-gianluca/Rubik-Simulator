import OpenGL
# PyOpenGL calls glGetError after every GL call, which stalls the pipeline. Must be set
# before anything imports OpenGL.GL.
OpenGL.ERROR_CHECKING = False
import pygame
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from pygame.locals import *
from src import display_manager
from src import hdr as hdr_output
from src.loading_animation import LoadingAnimation
from src.game import Game


def prepare_process():
    """Process-wide setup that must happen before the first window exists."""
    display_manager.enable_dpi_awareness()


def main():
    print("Initializing the game...")

    prepare_process()
    pygame.init()

    # Resolve the saved display settings against the monitors that are actually connected
    from src.settings_manager import SettingsManager
    settings = SettingsManager()
    if settings.is_new_user:
        index = settings.settings.get("display_index", 0)
        w, h = display_manager.default_window_size(index)
        settings.settings["resolution"] = {"width": w, "height": h}
        settings.save_settings()
    mode, index, size = display_manager.resolve(settings.settings)
    use_hdr = bool(settings.settings.get("hdr_enabled", False)) and hdr_output.display_hdr_info(index)[0]
    paper_white = settings.settings.get("hdr_paper_white", hdr_output.PAPER_WHITE_DEFAULT)

    # Create and run the loading animation in the final window
    loading_animation = LoadingAnimation(mode, index, size, hdr=use_hdr, paper_white=paper_white)

    # Run the loading animation synchronously
    if loading_animation.run():
        print("Loading complete, starting game...")

        # Reuse the same window and OpenGL context for a seamless transition
        game = Game(existing_screen=loading_animation.screen)
        game.run()
    else:
        print("Loading cancelled or failed")

    # Clean up
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()

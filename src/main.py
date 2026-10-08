import sys

sys.dont_write_bytecode = True

from src.ui.app import RollingThunderApp


def main() -> None:
    RollingThunderApp().run()


if __name__ == "__main__":
    main()

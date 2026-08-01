from PyStreamingTool.ui.ui import CloseApp, RunApp


def main() -> None:
    try:
        while True:
            RunApp()
    except KeyboardInterrupt:
        CloseApp()


if __name__ == "__main__":
    main()

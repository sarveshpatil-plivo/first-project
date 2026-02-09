from checker import run_health_check

if __name__ == "__main__":
    success = run_health_check()
    exit(0 if success else 1)

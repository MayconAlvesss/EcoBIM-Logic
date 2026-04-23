import subprocess
import requests
import time
import os
import sys
import signal

# Robust Path Configurations
# Ensures the script works regardless of where it is called from
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
API_URL = "http://localhost:8000"
DOTNET_PROJECT = os.path.join(BASE_DIR, "Aura.Revit", "src", "Aura.Revit.csproj")
TESTS_DIR = os.path.join(BASE_DIR, "tests")
SIMULATOR_SCRIPT = os.path.join(BASE_DIR, "lab", "revit_to_api_simulator.py")

class EcobimAuditor:
    def __init__(self):
        self.api_process = None

    def log(self, msg, status="INFO"):
        icons = {"INFO": "🔵", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️"}
        print(f"{icons.get(status, '⚪')} [{status}] {msg}")

    def check_dependencies(self):
        """Checks if necessary tools are in PATH."""
        self.log("Checking system dependencies...")
        try:
            # Using encoding and errors to avoid UnicodeDecodeError on Windows
            subprocess.run(["dotnet", "--version"], check=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
            self.log("Dotnet SDK detected.", "SUCCESS")
        except Exception:
            self.log("Dotnet SDK not found or error checking. C# compilation test may fail.", "WARN")

    def run_unit_tests(self):
        """Runs Pytest tests."""
        self.log("Starting Unit Tests (Pytest)...")
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = BASE_DIR

            result = subprocess.run(
                [sys.executable, "-m", "pytest", TESTS_DIR],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env
            )
            if result.returncode == 0:
                self.log("Unit tests passed!", "SUCCESS")
                return True
            else:
                self.log(f"Unit tests failed (Return code {result.returncode}):\n{result.stdout}", "ERROR")
                return False
        except Exception as e:
            self.log(f"Critical error running Pytest: {e}", "ERROR")
            return False

    def compile_csharp(self):
        """Tries to compile the Revit Add-in project."""
        self.log("Attempting to compile the Revit Add-in (C#)...")
        if not os.path.exists(DOTNET_PROJECT):
            self.log(f"C# project not found at: {DOTNET_PROJECT}", "ERROR")
            return False

        try:
            # Force UTF-8 and character replacement to prevent decoding crash
            result = subprocess.run(
                ["dotnet", "build", DOTNET_PROJECT],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            if result.returncode == 0:
                self.log("C# compilation successful!", "SUCCESS")
                return True
            else:
                # The error will be displayed even with special characters
                output = result.stdout if result.stdout else result.stderr
                self.log(f"C# compilation error:\n{output}", "ERROR")
                return False
        except Exception as e:
            self.log(f"Could not execute C# build: {e}", "ERROR")
            return False

    def start_api(self):
        """Starts the FastAPI API in the background."""
        self.log("Starting Aura Core API...")
        try:
            # PYTHONPATH ensures uvicorn finds the 'api' module
            env = os.environ.copy()
            env["PYTHONPATH"] = BASE_DIR

            self.api_process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=BASE_DIR,
                env=env
            )

            # Wait for API to come online (10s timeout)
            for _ in range(10):
                try:
                    if requests.get(API_URL, timeout=1).status_code == 200:
                        self.log("API Online!", "SUCCESS")
                        return True
                except:
                    time.sleep(1)

            self.log("The API took too long to respond or did not start.", "ERROR")
            return False
        except Exception as e:
            self.log(f"Failed to start API process: {e}", "ERROR")
            return False

    def run_integration_sim(self):
        """Runs the Revit simulator to test the data flow."""
        self.log("Starting BIM Integration Simulator...")
        if not os.path.exists(SIMULATOR_SCRIPT):
            self.log("Simulator script not found.", "ERROR")
            return False

        try:
            result = subprocess.run(
                [sys.executable, SIMULATOR_SCRIPT],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            if "success" in result.stdout.lower() or result.returncode == 0:
                self.log("Data flow simulation completed!", "SUCCESS")
                return True
            else:
                self.log(f"Simulation failed:\n{result.stdout}", "ERROR")
                return False
        except Exception as e:
            self.log(f"Error running simulator: {e}", "ERROR")
            return False

    def shutdown(self):
        """Shuts down the API and cleans up processes."""
        if self.api_process:
            self.log("Shutting down API processes...")
            try:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.api_process.pid)], capture_output=True)
                else:
                    os.killpg(os.getpgid(self.api_process.pid), signal.SIGTERM)
            except:
                self.api_process.terminate()

    def execute_full_audit(self):
        print("\n" + "="*50)
        print("   ECOBIM SYSTEM AUDIT - FULL CHECKUP   ")
        print("="*50)

        self.check_dependencies()

        # Tests that do not depend on the API being online
        results = {
            "Unit Tests": self.run_unit_tests(),
            "C# Compilation": self.compile_csharp(),
        }

        # Tests that depend on the API
        if self.start_api():
            results["Integration Sim"] = self.run_integration_sim()
            self.shutdown()
        else:
            results["Integration Sim"] = False

        print("\n" + "="*50)
        print("FINAL REPORT")
        for test, status in results.items():
            color = "PASSED" if status else "FAILED"
            print(f"{test.ljust(20)}: {color}")
        print("="*50 + "\n")

if __name__ == "__main__":
    auditor = EcobimAuditor()
    try:
        auditor.execute_full_audit()
    except KeyboardInterrupt:
        auditor.shutdown()
        print("\nAudit interrupted by user.")

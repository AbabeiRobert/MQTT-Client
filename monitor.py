import psutil
import platform
import time
import os

class SystemMonitor:
    def __init__(self):
        pass
    # Returneaza procentul de utilizare CPU (non-blocant)
    # In caz de eroare la citire, returneaza o valoare safe (0.0)
    def get_cpu_usage(self):
        try:
            return psutil.cpu_percent(interval=None)
        except:
            return 0.0
    # Returneaza procentul de memorie virtuala utilizata
    def get_memory_usage(self):
        try:
            return psutil.virtual_memory().percent
        except:
            return 0.0

    def get_temperature(self):
        # Temperatura este foarte dependentă de OS/Hardware
        # Încercăm o implementare generică pt Linux
        try:
#cautam toti senzorii de temperatura disponibili;daca nu gasim nimic returnam 0
            temps = psutil.sensors_temperatures()
            if not temps:
                return 0.0
#daca exista ceva returnam primul rezultat gasit
            for name, entries in temps.items():
                for entry in entries:
                    if entry.current:
                        return entry.current
            return 0.0
        except Exception:
            return 0.0
#returnam toate metricele colectate
    def collect_metrics(self):
        return {
            "cpu": self.get_cpu_usage(),
            "ram": self.get_memory_usage(),
            "temperatura": self.get_temperature()
        }

if __name__ == "__main__":
    mon = SystemMonitor()
    print("Test monitor:", mon.collect_metrics())

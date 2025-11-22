import psutil
import platform


class SystemMonitor:
    def __init__(self):
        self.os_type = platform.system()
        psutil.cpu_percent(interval=None)

    def get_cpu_load(self):
        return psutil.cpu_percent(interval=None)

    def get_memory_usage(self):
        return psutil.virtual_memory().percent

    def get_temperature(self):
        try:
            temps = psutil.sensors_temperatures() #este un dictionar unde valorea temperaturii este .current
            if not temps:
                return None
            for name, entries in temps.items():
                if 'cpu' in name.lower() or 'core' in name.lower() or 'package' in name.lower(): #difera in functie de dispozitivul pe care se ruleaza
                    for entry in entries:
                        if entry.current > 0:
                            return entry.current
            first_key = next(iter(temps)) #daca denumirile nu sunt gasite, se ia primul element din dictionar
            if temps[first_key]:
                return temps[first_key][0].current
        except Exception:
            return None
        return None

    def collect_metrics(self):
        metrics = {
            "cpu": self.get_cpu_load(),
            "ram": self.get_memory_usage(),
            "temperatura": self.get_temperature()
        }

        if metrics["temperatura"] is None:
            metrics["temperatura"] = 0.0

        return metrics
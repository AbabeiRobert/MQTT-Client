import psutil
import random

class SystemMonitor:
    def __init__(self):
        pass

    def collect_metrics(self):
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent

        try:
            temps = psutil.sensors_temperatures()
            if "coretemp" in temps:
                temperatura = temps["coretemp"][0].current
            elif "cpu_thermal" in temps:
                temperatura = temps["cpu_thermal"][0].current
            else:
                temperatura = random.uniform(30, 70)
        except:
            temperatura = random.uniform(30, 70)

        return {
            "cpu": cpu,
            "ram": ram,
            "temperatura": temperatura
        }

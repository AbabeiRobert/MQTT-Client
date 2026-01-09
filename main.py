import tkinter as tk
from gui import MQTTGui

def main():
#creeaza fereastra principala (root) a aplicatiei Tkinter si initializeaza sistemul GUI
    root = tk.Tk()
#creeaza obiectul aplicatiei GUI si populeaza fereastra root cu widget-uri
    app = MQTTGui(root)
    try:
#porneste bucla de evenimente Tkinter si mentine aplicatia activa
        root.mainloop()
    except KeyboardInterrupt:
        print("\nAplicatia a fost oprita fortat (Ctrl+C).")
        try:
            if app.client:
#inchide socketul MQTT daca exista o conexiune activa
                app.client.sock.close()
#distruge fereastra principala si opreste interfata grafica
            root.destroy()
        except:
#ignora eventualele erori aparute la inchidere
            pass

if __name__ == "__main__":
    main()

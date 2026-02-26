# controller_instance.py
# This file holds the controller globally to avoid circular imports

controller = None

def init_controller(ctrl):
    global controller
    controller = ctrl

def get_controller():
    return controller
import pygame

def print_controller_input():
    pygame.init()
    joystick_count = pygame.joystick.get_count()

    if joystick_count == 0:
        print("No joystick detected.")
        return

    joystick = pygame.joystick.Joystick(0)
    joystick.init()

    print(f"Detected joystick: {joystick.get_name()}")
    print(f"Number of axes: {joystick.get_numaxes()}")
    print(f"Number of buttons: {joystick.get_numbuttons()}")
    print(f"Number of hats: {joystick.get_numhats()}")

    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.JOYAXISMOTION:
                    print(f"Axis {event.axis}: {event.value:.4f}")
                elif event.type == pygame.JOYBUTTONDOWN:
                    print(f"Button {event.button} pressed.")
                elif event.type == pygame.JOYBUTTONUP:
                    print(f"Button {event.button} released.")
                elif event.type == pygame.JOYHATMOTION:
                    print(f"Hat {event.hat}: {event.value}")
            pygame.time.wait(10) # Small delay to prevent busy-waiting
    except KeyboardInterrupt:
        print("Exiting controller input reader.")
    finally:
        pygame.quit()

if __name__ == "__main__":
    print_controller_input()

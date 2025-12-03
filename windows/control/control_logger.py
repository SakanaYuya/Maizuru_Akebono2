# コントローラーの入力をログファイルに記録するテスト用コード

import pygame
import datetime
import logging

def log_controller_input():
    # --- Logger Setup ---
    # Create a unique log file name with a timestamp
    log_filename = f"logs/controller_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Configure logging to write to the file
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(message)s',
        filename=log_filename,
        filemode='w' # Overwrite the file if it exists
    )
    
    # Also, create a handler to print messages to the console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    console_handler.setFormatter(formatter)
    logging.getLogger('').addHandler(console_handler)

    # --- Pygame Initialization ---
    pygame.init()
    joystick_count = pygame.joystick.get_count()

    if joystick_count == 0:
        logging.info("No joystick detected.")
        return

    joystick = pygame.joystick.Joystick(0)
    joystick.init()

    logging.info(f"Detected joystick: {joystick.get_name()}")
    logging.info(f"Number of axes: {joystick.get_numaxes()}")
    logging.info(f"Number of buttons: {joystick.get_numbuttons()}")
    logging.info(f"Number of hats: {joystick.get_numhats()}")
    logging.info("--- Starting input logging ---")

    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.JOYAXISMOTION:
                    logging.info(f"Axis {event.axis}: {event.value:.4f}")
                elif event.type == pygame.JOYBUTTONDOWN:
                    logging.info(f"Button {event.button} pressed.")
                elif event.type == pygame.JOYBUTTONUP:
                    logging.info(f"Button {event.button} released.")
                elif event.type == pygame.JOYHATMOTION:
                    logging.info(f"Hat {event.hat}: {event.value}")
            pygame.time.wait(10) # Small delay to prevent busy-waiting
    except KeyboardInterrupt:
        logging.info("--- Stopping controller input logger ---")
    finally:
        pygame.quit()

if __name__ == "__main__":
    log_controller_input()

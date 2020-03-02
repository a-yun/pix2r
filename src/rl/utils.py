objects = [ 
            'button_top', 
            'button_side', 
            'coffee_button', 
            'handle_press_top',
            'handle_press_side',
            'door_lock',
            'door_unlock',
            'dial_turn',
            'faucet_open',
            'faucet_close',
            'window_open',
            'window_close',
            'peg_unplug',
            'button_top_2', 
            'button_side_2', 
            'coffee_button_2', 
            'handle_press_top_2',
            'handle_press_side_2',
            'door_lock_2',
            'door_unlock_2',
            'dial_turn_2',
            'faucet_open_2',
            'faucet_close_2',
            'window_open_2',
            'window_close_2',
            'peg_unplug_2',
        ]

obj2grp = {
            'button_top': 'button_top', 
            'button_side': 'button_side', 
            'coffee_button': 'coffee_button', 
            'handle_press_top': 'handle_press_top',
            'handle_press_side': 'handle_press_side',
            'door_lock': 'door',
            'door_unlock': 'door',
            'dial_turn': 'dial_turn',
            'faucet_open': 'faucet',
            'faucet_close': 'faucet',
            'window_open': 'window',
            'window_close': 'window',
            'peg_unplug': 'peg_unplug',
            'button_top_2': 'button_top_2', 
            'button_side_2': 'button_side_2', 
            'coffee_button_2': 'coffee_button_2', 
            'handle_press_top_2': 'handle_press_top_2',
            'handle_press_side_2': 'handle_press_side_2',
            'door_lock_2': 'door_2',
            'door_unlock_2': 'door_2',
            'dial_turn_2': 'dial_turn_2',
            'faucet_open_2': 'faucet_2',
            'faucet_close_2': 'faucet_2',
            'window_open_2': 'window_2',
            'window_close_2': 'window_2',
            'peg_unplug_2': 'peg_unplug_2',
        }

def enable_gpu_rendering():
    # This is a hack to enable GPU rendering.
    from dm_control import mujoco
    # Load a model from an MJCF XML string.
    xml_string = """
    <mujoco>
      <worldbody>
        <light name="top" pos="0 0 1.5"/>
        <geom name="floor" type="plane" size="1 1 .1"/>
        <body name="box" pos="0 0 .3">
          <joint name="up_down" type="slide" axis="0 0 1"/>
          <geom name="box" type="box" size=".2 .2 .2" rgba="1 0 0 1"/>
          <geom name="sphere" pos=".2 .2 .2" size=".1" rgba="0 1 0 1"/>
        </body>
      </worldbody>
    </mujoco>
    """

    physics = mujoco.Physics.from_xml_string(xml_string)
    # Render the default camera view as a numpy array of pixels.
    pixels = physics.render()


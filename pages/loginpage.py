# pages/loginpage.py

def perform_actions(page, actions, logger=None):
    for action in actions:
        if logger:
            logger.info(f" -> {action}")
        try:
            if action['action'] == 'click':
                page.click(action['selector'])
            elif action['action'] in ['type', 'fill']:
                page.fill(action['selector'], action['value'])
            elif action['action'] == 'upload':
                page.set_input_files(action['selector'], action['value'])
        except Exception as e:
            if logger:
                logger.error(f"Failed to perform action {action}: {e}")
            else:
                print(f"Failed to perform action {action}: {e}")

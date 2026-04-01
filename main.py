from app.main import start_bot

import asyncio


if __name__ == '__main__':
    # from app.utils.generate_demo_messages import main as generate_demo_messages
    # asyncio.run(generate_demo_messages())

    asyncio.run(start_bot())
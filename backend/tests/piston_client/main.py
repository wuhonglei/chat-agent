import asyncio

from pyston import File, PystonClient


async def main() -> None:
    client = PystonClient(base_url="http://1.12.53.9:2000/api/v2/")
    output = await client.execute("python", [File("print('Hello world')")])
    await client.close_session()
    print(output)


asyncio.run(main())

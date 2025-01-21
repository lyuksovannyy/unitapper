import argparse
import asyncio
import sys
from os import _exit

from src import terminal, launcher, webpanel

if __name__ == "__main__":
    async def main() -> None:
        parser = argparse.ArgumentParser(description="Process some boolean arguments.")
        parser.add_argument("-option", type=int, help="Option number", default=None)
        parser.add_argument("-script", type=str, help="[DEV] Start writen script immideatly", default=None)
        parser.add_argument("-session", type=str, help="[DEV] Select session", default=None)
        try:
            args = parser.parse_args()
        except SystemExit:
            args = {}
            for arg in sys.argv:
                if " " in arg:
                    parts = arg.split(" ")
                    k, v = parts[0], parts[1]
                    args[k] = v
            class args:
                option = args.get("option")
                script = args.get("script")
                session = args.get("session")
            
        programm = launcher(args.script, args.session)
        webpanel.start()
        
        while True:
            try:
                await programm.show()
                
                #if args.script:
                option = "1"
                #else:
                #option = terminal.input(" &gray> ", forced_input=args.option)
                #    args.option = None
                
                if not option.isdigit():
                    programm.output = "&redInput must be a number."
                    continue
                
                state = await programm.select_option(int(option))
                
                if state and option == "1":
                    args.option = "1"
                
                if not state:
                    programm.output = "&redProvided number isn't valid."
                
                elif state == "stop":
                    programm.output = "Stopped."
                    await programm.show()
                    break
                
                elif state == "empty":
                    programm.output = "&redNo scripts or sessions we're found."
                    args.option = None
                    args.script = None
                else:
                    await asyncio.sleep(1e300)
                
            except KeyboardInterrupt or SystemExit or asyncio.CancelledError:
                break
            
        terminal.write("\nSee you soon!")
        _exit(0)
        
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
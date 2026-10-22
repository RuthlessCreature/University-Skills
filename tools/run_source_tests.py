"""Run local source tests with a durable log and explicit process exit code."""
from pathlib import Path
import argparse,subprocess,sys

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--log',required=True);args=parser.parse_args()
    target=Path(args.log)
    if target.exists():raise FileExistsError('Preserve existing test logs')
    command=[sys.executable,'-X','utf8','-m','unittest','discover','-s',str(Path(__file__).resolve().parents[1]/'tests'),'-p','test_*.py']
    result=subprocess.run(command,capture_output=True);data=result.stdout+result.stderr
    with target.open('xb') as stream:stream.write(data)
    print(data.decode('utf-8','replace'));return result.returncode

if __name__=='__main__':sys.exit(main())

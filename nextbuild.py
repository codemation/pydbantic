"""
Purpose:
Increments current Pypi version by .001

Usage: 
    pip3 download aiopyql && ls aiopyql*.whl | sed 's/-/" "/g' | awk '{print "(" $2 ")"}' |  python3 python/aiopyql/aiopyql/nextbuild.py
"""
if __name__=='__main__':
    import sys
    version = sys.stdin.readline().rstrip()
    if '(' in version and ')' in version:
        version = version[2:7]
        print(f"{version[:-1]}{int(version[-1])+1}")
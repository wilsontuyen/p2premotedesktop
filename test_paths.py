import sys, os, builtins
print('sys.frozen:', getattr(sys, 'frozen', False))
print('__compiled__ in globals():', '__compiled__' in globals())
try:
    print('__compiled__ in builtins:', hasattr(builtins, '__compiled__'))
except Exception as e:
    print('builtins check error:', e)
try:
    print('sys has __compiled__:', hasattr(sys, '__compiled__'))
except Exception as e:
    pass

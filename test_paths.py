import sys, os
print('sys.frozen:', getattr(sys, 'frozen', False))
print('sys.executable:', sys.executable)
print('sys.argv[0]:', sys.argv[0])
print('__file__:', __file__)

#
#    merge_sol script.
#
#    it does move all children in work to a new sol,
#    which is named like case1, case2....
#
#
#    this script will be used when model does not have
#    a particular finishg_script.
#
#
#
#    copy this to your model and set finish_script in setting panel
#                          or
#    edit this file and leave the finish_script blank
#
#    this script will be called using RunA(k, worker, sol)
#    writing the data is critical part and user needs to
#    use a lock. Use PySol.aquire_lock() PySol.release_lock()
#
from ifigure.mto.py_code import PySol
sol = args[2]
worker = args[1]
index = args[0]

# sol.aquire_lock()
# print 'worker', worker
# print 'solution', sol


name = 'case' + str(index)
if sol.has_child(name):
    print(('removing ', name))
    sol.get_child(name=name).destroy()
print(('merging solution index=', index))
ps = PySol()
sol.add_child(name, ps)

for name, child in worker.get_children():
    if name == 'parameters':
        child.duplicate(ps, 'parameters')
    else:
        child.move(ps, keep_zorder=False)

# sol.release_lock()

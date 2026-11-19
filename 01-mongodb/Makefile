ANSIBLE := ansible-playbook
OPS := ops.yml

.PHONY: deploy status stop start restart reboot-check rbac-setup rbac-grant \
	rbac-revoke rbac-modify rbac-trial rbac-matrix backup-one backup-all backup-again \
	restore monitor-check load tunnel

deploy:
	$(ANSIBLE) site.yml

status:
	$(ANSIBLE) $(OPS) --tags status
stop:
	$(ANSIBLE) $(OPS) --tags stop
start:
	$(ANSIBLE) $(OPS) --tags start
restart:
	$(ANSIBLE) $(OPS) --tags restart
reboot-check:
	$(ANSIBLE) $(OPS) --tags reboot-check

rbac-setup:
	$(ANSIBLE) $(OPS) --tags rbac-setup
rbac-grant:
	$(ANSIBLE) $(OPS) --tags rbac-grant
rbac-revoke:
	$(ANSIBLE) $(OPS) --tags rbac-revoke
rbac-modify:
	$(ANSIBLE) $(OPS) --tags rbac-modify
rbac-trial:
	$(ANSIBLE) $(OPS) --tags rbac-trial
rbac-matrix:
	$(ANSIBLE) $(OPS) --tags rbac-matrix

backup-one:
	$(ANSIBLE) $(OPS) --tags backup-one
backup-all:
	$(ANSIBLE) $(OPS) --tags backup-all
backup-again:
	$(ANSIBLE) $(OPS) --tags backup-again
restore:
	$(ANSIBLE) $(OPS) --tags restore

monitor-check:
	$(ANSIBLE) $(OPS) --tags monitor-check
load:
	$(ANSIBLE) $(OPS) --tags load

tunnel:
	ssh -N -L 13000:127.0.0.1:3000 mikhail@192.168.64.2

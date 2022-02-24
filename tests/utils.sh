# custom wrapper around juju to wait for model to be active
myjuju () {
	juju "$@"

	# sometimes juju need a second to start jujuing
	sleep 2

	# wait for everything to be active
	juju wait-for application slurmctld --query='status=="active"' --timeout=9m > /dev/null 2>&1
	juju wait-for application slurmdbd --query='status=="active"' --timeout=9m > /dev/null 2>&1
	juju wait-for application slurmrestd --query='status=="active"' --timeout=9m > /dev/null 2>&1

	# slurmd might need a reboot, ignore it
	juju wait-for application slurmd --query='status=="active" || status=="blocked"' --timeout=9m > /dev/null 2>&1
}

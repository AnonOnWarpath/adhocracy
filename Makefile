# Workaround Makefile for cleanup

RM = rm -rf
AG = apt-get -y install --no-install-recommends

.PHONY: clean

deb-install:
	@$(AG) python-lxml
	@$(AG) python-imaging
	@$(AG) python-pastescript
	@$(AG) python-mysqldb
	@$(AG) python-sqlite
	@$(AG) python-pgsql

prebuildout: deb-install
	python bootstrap.py

buildout: prebuildout
	bin/buildout

clean:
	@find . \( \
		-iname "*.pyc" \
		-or -iname "*.pyo" \
		\) -delete

distclean: clean
	@$(RM) \
		bin/ \
		build/ \
		develop-eggs/ \
		dist/ \
		docs/doctrees/ \
		docs/html/ \
		docs/make.bat \
		docs/Makefile \
		eggs/ \
		parts/ \
		src/*.egg-info/ \
		MANIFEST \
		.installed.cfg


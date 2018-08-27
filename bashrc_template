# .bashrc login initialization script for serviceb account
#
# Configure the system properly for UNIX builds of CM, OM, OMI, etc.
# In general, PATH data belongs in .bashrc; all else belongs in .bash_profile.
#
# IMPORTANT: This file is checked into git!  Any edits should be done there!

# Note: Build systems don't use 'tf' anymore, so don't deal with that

# Save paths so, if we re-run ourselves, the path doesn't get needlessly long

if [ "${SAVED_PATH:-==Unset==}" = "==Unset==" ]; then
    export SAVED_PATH="${PATH}"
else
    export PATH="${SAVED_PATH}"
fi

if [ "${SAVED_LD_LIBRARY_PATH:-==Unset==}" = "==Unset==" ]; then
    export SAVED_LD_LIBRARY_PATH="${LD_LIBRARY_PATH}"
else
    export LD_LIBRARY_PATH="${SAVED_LD_LIBRARY_PATH}"
fi

# Generic settings by O/S

case `uname -s` in
    AIX)
	PATH=/usr/bin:/usr/local/bin:/usr/sbin:/usr/vacpp/bin:/opt/freeware/bin:$PATH
	PATH=$PATH:/opt/pware/samba/3.0.26a/bin:/usr/java5/jre/bin
	export PATH

	export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/usr/dt/lib:/usr/local/lib
	export PKG_CONFIG_PATH=/usr/local/lib/pkgconfig:/usr/lib/pkgconfig

	# Make sure artificial limits don't cause problems
	ulimit -m unlimited -n unlimited -s hard
	;;

    Darwin)
	# Not currently building on Mac OS/X systems
	;;

    HP-UX)
	PATH=$PATH:/usr/sbin:/opt/samba/bin:/opt/java1.5/jre/bin:/opt/aCC/bin:/opt/ansic/bin:/usr/local/bin
	export PATH

        # HP utilities are very sensitive to locale, and some don't work with utf8
        LANG=C
        export LANG

        # Bash alias won't work in configure scripts; set path for make instead
        if [ ! -f ~/bin/make ]; then
            mkdir -p ~/bin
            ln -s /usr/local/bin/gmake ~/bin/make
        fi
        export PATH=~/bin:$PATH

        # Deal with OpenSSL linkages properly with pkg-config

        case `uname -m` in
            ia64)	# ia64
		export PKG_CONFIG_PATH=/opt/openssl/lib/hpux32/pkgconfig
	        ;;

            9000/800)	# pa-risc
                export PKG_CONFIG_PATH=/opt/openssl/lib/pkgconfig
                ;;

            *)
                echo "ERROR: Unknown platform, check output of uname -m"
                exit 1
                ;;
        esac
        ;;

    Linux)
	# Support Bullseye if installed (Note: Bullseye needs to be at start of path)
	if [ -d /opt/Bullseye/bin ]; then
	    export PATH=/opt/Bullseye/bin:$PATH
	fi

	export PATH=$PATH:/usr/bin:/usr/local/bin:/usr/sbin
	;;

    SunOS)
	# Sun systems put software in an unusual spot (generally not on path)
	if [ `uname -r` == '5.11' ]; then
	    export MANPATH="/usr/share/man:/opt/solstudio12.2/man"
	    export PATH="$PATH:/usr/bin:/usr/local/bin:/usr/sbin:/usr/gnu/bin:/opt/solstudio12.2/bin:/opt/csw/bin"
	else
	    # Support Bullseye if installed (Note: Bullseye needs to be at start of path)
	    if [ -d /opt/Bullseye/bin ]; then
		export PATH=/opt/Bullseye/bin:$PATH
	    fi

	    export MANPATH="/usr/share/man:/usr/sfw/man:/opt/sfw/man:/opt/SUNWspro/man:/usr/local/man"
	    export PATH="$PATH:/usr/sbin:/usr/local/bin:/usr/sfw/bin:/opt/sfw/bin"
	    export PATH="$PATH:/opt/SUNWspro/bin:/opt/SUNWspro/prod/bin:/opt/csw/bin"
	fi

	if [ `uname -r` == '5.8' -o `uname -r` == '5.9' ]; then
	    # Fix up LD_LIBRARY_PATH so we can run openssl ...
	    export LD_LIBRARY_PATH=/usr/lib:/usr/local/lib:/usr/local/ssl/lib
	fi
	;;

    *)
	;;
esac

LEAPS
=====

Lothians Equal Access Programme for Schools 

Online questionnaire management software.

Not something that is of any use to anyone else.


Installing the leaps VM
=======================

configure the network host in /etc/network/interfaces, add the following (find the right hardware name if reconfiguring on new vm):
auto ens160
iface ens160 inet static
address 129.215.10.235
netmask 255.255.254.0
gateway 129.215.11.254
dns-nameservers 8.8.8.8 8.8.4.4

sudo apt-get install openssh-server
sudo apt-get install htop

cd
mkdir .ssh
chmod 700 .ssh
mv /root/.ssh/authorized_keys .ssh/
touch .ssh/authorized_keys
chmod 600 .ssh/authorized_keys

Copy nay necessary public keys into the authorized_keys file

sudo visudo, and add the following:
leaps ALL=(ALL) NOPASSWD: ALL

sudo vim /etc/ssh/sshd_config and edit:
PermitRootLogin no
PasswordAuthentication no
PubkeyAcceptedKeyTypes=+ssh-dss

sudo service ssh restart

sudo apt-get install nginx

sudo apt-get -q -y install bpython screen git-core python-pip python-dev python-setuptools build-essential python-software-properties

sudo pip install --upgrade pip
sudo pip install --upgrade virtualenv
sudo pip install gunicorn
sudo pip install requests
sudo pip install supervisor

cd /etc/init.d
copied supervisord from my test machine
sudo chmod a+x /etc/init.d/supervisord
sudo chown root:root supervisord
sudo service supervisord stop
sudo update-rc.d supervisord defaults
sudo mkdir /var/log/supervisor
sudo ln -s /usr/local/bin/supervisord /usr/bin/supervisord
cd /etc
sudo mkdir supervisor
cd supervisor
sudo mkdir conf.d
copied supervisord.conf from my test machine
sudo chown root:root supervisord.conf
sudo service supervisord start


Install elasticsearch 0.90.2
============================

sudo apt-get install default-jre

cd /home/leaps
curl -L https://download.elasticsearch.org/elasticsearch/elasticsearch/elasticsearch-0.90.2.tar.gz -o elasticsearch.tar.gz
tar -xzvf elasticsearch.tar.gz
ln -s elasticsearch-0.90.2 elasticsearch
cd elasticsearch/bin
git clone git://github.com/elasticsearch/elasticsearch-servicewrapper.git
cd elasticsearch-servicewrapper
git checkout 0.90
mv service ../
cd ../
sudo rm -R elasticsearch-servicewrapper
sudo ln -s /home/leaps/elasticsearch/bin/service/elasticsearch /etc/init.d/elasticsearch
sudo update-rc.d elasticsearch defaults

# vim config/elasticsearch.yml and uncomment bootstrap.mlockall true
# and uncomment cluster.name: elasticsearch and change to leaps

# vim bin/service/elasticsearch.conf and set.default.ES_HEAP_SIZE=2048
# and set wrapper.logfile.loglevel wrapper.logfile.maxsize wrapper.logfile.maxfiles to WARN 100m and 20

sudo /etc/init.d/elasticsearch start


Clone and install LEAPS
=======================

sudo apt-get install libxml2-dev libxslt1-dev libffi-dev python-lxml
virtualenv -p python2.7 --no-site-packages leaps
cd leaps
mkdir src
cd src
git clone https://github.com/CottageLabs/leaps.git
cd leaps
source ../../bin/activate
pip install gunicorn
pip install eventlet==0.20
pip install lxml
python setup.py install
pip install -e .

# copy the app.cfg from the live service to the new service


Symlink LEAPS nginx and supervisor configs
==========================================

cd /etc/nginx/sites-enabled
sudo ln -s ~/leaps/src/leaps/config/nginx/leaps .
sudo nginx -t
sudo service nginx restart
cd /etc/supervisor/conf.d
sudo ln -s ~/leaps/src/leaps/config/supervisor/leaps.conf .
sudo supervisorctl update


Setup certbot SSL
=================

sudo apt-get update
sudo apt-get install software-properties-common
sudo add-apt-repository ppa:certbot/certbot
sudo apt-get update
sudo apt-get install python-certbot-nginx
sudo certbot --nginx


Transfer data
=============

Just copying the elasticsearch data folder over is the easiest way, then name it the same 
as the cluster name, and restart elasticsearch and LEAPS.



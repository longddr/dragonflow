# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from oslo_log import log as logging
from oslo_utils import importutils

import eventlet
from stevedore import driver
import sys

from dragonflow._i18n import _, _LE
import greenlet

DF_PUBSUB_DRIVER_NAMESPACE = 'dragonflow.pubsub_driver'
LOG = logging.getLogger(__name__)

eventlet.monkey_patch()


def load_driver(driver_cfg, namespace):
    try:
        # Try to resolve by alias
        mgr = driver.DriverManager(namespace, driver_cfg)
        class_to_load = mgr.driver
    except RuntimeError:
        e1_info = sys.exc_info()
        # try with name
        try:
            class_to_load = importutils.import_class(driver_cfg)
        except (ImportError, ValueError):
            LOG.error(_LE("Error loading class %(class)s by alias e: %(e)s")
                    % {'class': driver_cfg, 'e': e1_info},
                    exc_info=e1_info)
            LOG.error(_LE("Error loading class by class name"),
                      exc_info=True)
            raise ImportError(_("Class not found."))
    return class_to_load()


class DFDaemon(object):

    def __init__(self, is_not_light=False):
        super(DFDaemon, self).__init__()
        self.pool = eventlet.GreenPool()
        self.is_daemonize = False
        self.thread = None
        self.is_not_light = is_not_light

    def daemonize(self, run):
        if self.is_daemonize:
            LOG.error(_LE("already daemonized"))
            return
        self.is_daemonize = True
        if self.is_not_light:
            self.thread = self.pool.spawn(run)
        else:
            self.thread = self.pool.spawn_n(run)
        eventlet.sleep(0)
        return self.thread

    def stop(self):
        if self.is_daemonize and self.thread:
            eventlet.greenthread.kill(self.thread)
            eventlet.sleep(0)
            self.thread = None
            self.is_daemonize = False

    def wait(self, timeout=None):
        if not self.is_daemonize or not self.thread:
            return False
        if timeout and timeout > 0:
            timeout_obj = eventlet.Timeout(timeout)
        try:
            self.thread.wait()
        except greenlet.GreenletExit:
            return True  # Good news
        finally:
            if timeout_obj:
                timeout_obj.cancel()

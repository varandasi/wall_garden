import { application } from 'controllers/application'

import AutoRefreshController from 'controllers/auto_refresh_controller'
application.register('auto-refresh', AutoRefreshController)

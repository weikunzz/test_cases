import component from './beaker'
import Jobs from './jobs'
import Statistics from './statistics'

export default {
  path: 'beaker', // Need to be uniq, and will be used for url routing
  icon: '<i class="fa fa-flask" aria-hidden="true"></i>', // Or import a webpack resource
  title: 'Beaker Plugin',
  entry: component,
  children: [
    {
      path: 'jobs',
      component: Jobs
    },
    {
      path: 'statistics',
      component: Statistics
    },
    {
      path: '',
      redirect: '/beaker/jobs'
    }
  ]
}

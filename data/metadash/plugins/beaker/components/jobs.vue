<template>
  <div>
    <bs-modal title="Cancel Jobs" effect="fade" width="800" :value="cancelModalShown" @closed="showCancelModal(false)" large>
      <h2><strong> Cancel following jobs? </strong></h2>
      <table class="table table-striped table-bordered table-hover table-condensed table-response">
        <tbody>
          <tr v-for="job in selected">
            <td v-for="attr in jobAttributes"> {{job[attr]}} </td>
          </tr>
        </tbody>
      </table>
      <div>
        <div v-if="cancelling" class="progress">
          <bs-progressbar :now="cancelProgress" label danger :type="cancelFailed ? 'danger': 'primary'" striped animated></bs-progressbar>
        </div>
      </div>
      <div slot="modal-footer">
        <div v-if="cancelInfo" style='margin-left: 10px; margin-right: 10px;' class="alert" :class="{ 'alert-danger': cancelFailed, 'alert-info': !cancelFailed }" >
          <strong> {{ cancelInfo }} </strong>
          <div clsss="well" v-if="cancelCmd">
            <code> <strong> {{ cancelCmd }} </strong> </code>
          </div>
        </div>
        <div class="form-group" style="padding-left: 10px;">
          <button class="btn btn-danger" type="button" id="deleteRows1" @click="cancelSelectedJob" :class="{ disabled: !!cancelling }">Cancel Selected Jobs</button>
          <button class="btn btn-default" type="button" id="restoreRows1" @click="showCancelModal(false)">Close</button>
        </div>
      </div>
    </bs-modal>
    <!-- TODO: Simplify with Toolbar -->
    <div class="row toolbar-pf table-view-pf-toolbar">
      <div class="col-sm-12">
        <form class="toolbar-pf-actions">
          <div class="form-group toolbar-pf-filter">
            <label class="sr-only" for="filter">Job Type</label>
            <div class="input-group">
              <div class="input-group-btn">
                <bs-dropdown text="Change Job Type">
                  <li><a href="#" id="filter1">My Running Jobs</a></li>
                  <li><a href="#" id="filter2">My Group Running Jobs </a></li>
                  <li><a href="#" id="filter4">All Users' Running Jobs</a></li>
                </bs-dropdown>
                <bs-input :disabled="true" value="My Group Running Jobs">
                </bs-input>
              </div>
            </div>
          </div>
          <div class="form-group">
            <button class="btn btn-danger" type="button" id="deleteRows1" @click="showCancelModal(true)">Cancel Selected Jobs</button>
            <button class="btn btn-default" type="button" id="restoreRows1" disabled>Refresh</button>
            <div class="dropdown btn-group  dropdown-kebab-pf">
              <bs-dropdown text="Change Job Type">
                <span slot="button" class="fa fa-ellipsis-v"></span>
                <li><a href="#">WOW Such dropdown</a></li>
                <li role="separator" class="divider"></li>
                <li><a href="#">WOW Such separator</a></li>
              </bs-dropdown>
            </div>
          </div>
        </form>
        <div class="row toolbar-pf-results">
          <div class="col-sm-9">
            <div class="hidden">
              <h5>0 Results</h5>
              <p>Active filters:</p>
              <ul class="list-inline"></ul>
              <p><a href="#">Clear All Filters</a></p>
            </div>
          </div>
          <div class="col-sm-3 table-view-pf-select-results">
            <strong> {{selected.length}} </strong> of <strong> {{jobs.length}} </strong> selected
          </div>
        </div>
      </div>
    </div>
    <div class="job-table">
      <div v-if="!loading">
        <pf-table class="table-with-dropdown" v-if="jobs.length > 0" ref="jobTable"
          :hover="true" :stripe="true" :selectable="true" :sortable="true" :columns="jobAttributesNames" :rows="jobs"
          :sort-by="sortByName" :sort-direction="sortOrder"
          @sort-by="sortJob" @click="getSelectedJob">
          <template slot-scope="scope">
            <td v-for="attr in jobAttributes"> {{scope.row[attr]}} </td>
          </template>
          <template slot="action" slot-scope="scope">
            <div class="table-view-pf-btn">
              <button class="btn btn-default" type="button"> {{scope.row.jw_status.message || 'No Message'}} </button>
            </div>
          </template>
          <template slot="dropdown" slot-scope="scope">
            <li v-if="scope.row.jw_teardown"><a :href="scope.row.jw_teardown">Teardown Page</a></li>
            <li v-if="scope.row.jw_runtest"><a :href="scope.row.jw_runtest">Runtest Page</a></li>
            <li v-if="scope.row.jw_provision"><a :href="scope.row.jw_provision">Provision Page</a></li>
            <li role="separator" class="divider"></li>
            <li><a :href="scope.row.url">Beaker Page</a></li>
          </template>
        </pf-table>
        <h1 v-else>No Data</h1>
      </div>
      <horizon-loader :loading="loading"></horizon-loader>
    </div>
  </div>
</template>

<script>
import _ from 'lodash'
import JenkinsWorkflow from './jenkins-workflow'
import HorizonLoader from '@/components/HorizonLoader'
export default {
  name: 'beaker-jobs',
  components: { HorizonLoader },
  data () {
    return {
      loading: false,
      jobs: [],
      sortBy: 'id',
      sortOrder: 'desc',
      selected: [],
      jobAttributes: ['id', 'whiteboard', 'group', 'owner', 'status', 'result'],
      cancelling: false,
      cancelProgress: 0,
      cancelInfo: false,
      cancelFailed: false,
      cancelModalShown: false
    }
  },
  computed: {
    sortByName () {
      return this.jobAttributesNames[this.jobAttributes.indexOf(this.sortBy)]
    },
    jobAttributesNames () {
      return this.jobAttributes.map(_.upperFirst)
    }
  },
  methods: {
    refresh () {
      this.loading = true
      this.$http.get('/api/beaker-my-group-running-jobs/')
        .then(res => res.json())
        .then(jobs => {
          for (let job of jobs) {
            job.jw_status = { status: 'Loading', message: 'Loading' }
            job.jw_teardown = null
            job.jw_runtest = null
            job.jw_provision = null
            if (job.whiteboard.indexOf('libvirt-ci Jenkins URL') !== -1) {
              job.jw = new JenkinsWorkflow(job.whiteboard.substring(job.whiteboard.indexOf('http')))
              job.jw.fetchWorkflow()
                .then(() => job.jw.genStatus(),
                  () => job.jw.genStatus())
                .then(() => {
                  job.jw_teardown = job.jw.teardownBuild && job.jw.teardownBuild.url
                  job.jw_runtest = job.jw.runtestBuild && job.jw.runtestBuild.url
                  job.jw_provision = job.jw.provisionBuild && job.jw.provisionBuild.url
                  job.jw_status = {status: job.jw.status, message: job.jw.message}
                })
            } else {
              job.jw_status = { status: 'N/a', message: 'N/a' }
            }
          }
          this.jobs = jobs
        })
        .then(() => { this.loading = false })
        .catch(() => { this.loading = false })  // TODO
    },
    showCancelModal (show) {
      this.getSelectedJob()
      this.cancelInfo = 'To cancel the job, you can also run following command line:'
      this.cancelCmd = 'bkr job-cancel' + this.selected.map(x => ` J:${x.id}`).join('')
      this.cancelModalShown = show
    },
    sortJob (attr, order) {
      this.sortBy = this.jobAttributes[this.jobAttributesNames.indexOf(attr)]
      this.sortOrder = order
    },
    getSelectedJob () {
      this.selected = this.$refs.jobTable.getSelected()
      return this.selected
    },
    async cancelSelectedJob () {
      this.cancelling = true
      this.cancelInfo = ''
      this.cancelFailed = false
      this.cancelProgress = 0
      for (let i = 0, len = this.selected.length; i < len; i++) {
        this.cancelInfo = 'Cancelling Job ' + this.selected[i].id
        await this.$http.get('/api/beaker-cancel-job/' + this.selected[i].id)
          .then(res => res.json())
          .then(data => { this.calcenInfo = data.message })
          .catch((data) => data.json().then(data => {
            this.cancelFailed = true
            this.cancelInfo = `Error during calcelling Job: ${this.selected[i].id}: data.message`
          }, () => {
            this.cancelFailed = true
            this.cancelInfo = 'Unknown Issue'
          }))
        if (this.cancelFailed) {
          break
        }
        this.cancelInfo = 'Done'
        this.cancelProgress = Math.round(((i + 1.0) / len) * 100)
      }
      this.cancelling = false
      if (!this.cancelFailed) {
        this.cancelModalShown = false
      }
    }
  },
  watch: {
    sortOrder () {
      this.jobs = _.orderBy(this.jobs, this.sortBy, this.sortOrder)
    },
    sortBy () {
      this.jobs = _.orderBy(this.jobs, this.sortBy, this.sortOrder)
    }
  },
  mounted () {
    this.refresh()
  }
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
.table-with-dropdown {
  padding-bottom: 50px;
}
</style>

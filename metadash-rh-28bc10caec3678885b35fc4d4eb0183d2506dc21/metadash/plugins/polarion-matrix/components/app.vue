<template>
  <div>
    <pf-table class="table-with-dropdown" ref="jobTable"
      :hover="true" :stripe="true" :selectable="true" :columns="testrunColumns" :rows="testruns">
      <template slot-scope="scope">
        <td> {{scope.row['name']}} </td>
        <td> {{scope.row['timestamp']}} </td>
        <td> {{scope.row['status']}} </td>
        <td> {{scope.row['polarion-matrix-submit-status']}} </td>
        <td> {{scope.row['tags']}} </td>
      </template>
      <template slot="action" slot-scope="scope">
        <div class="table-view-pf-btn">
          <button class="btn btn-default" type="button" @click="submitTestrun(scope.row['uuid'])"> Submit </button>
        </div>
      </template>
      <template slot="dropdown" slot-scope="scope">
        <li> <router-link tag="a" :to="{ path: `/test-results/testrun/${scope.row['uuid']}/` }">Testrun Detail</router-link> </li>
        <li role="separator" class="divider"></li>
        <li v-if="scope.row['polarion-matrix-submit-status'] == 'success'"><a :href="scope.row['polarion-matrix-submit-url']">Polarion Page</a></li>
        <li v-if="scope.row['polarion-matrix-submit-log']"><a :href="scope.row['polarion-matrix-submit-log']">Submit Log</a></li>
      </template>
    </pf-table>
  </div>
</template>

<script>
import HorizonLoader from '@/components/HorizonLoader'
export default {
  data () {
    return {
      testruns: null,
      testrunColumns: ['Name', 'Timestamp', 'Status', 'Submit Status', 'Tags']
    }
  },
  components: { HorizonLoader },
  methods: {
    refresh () {
      this.$http.get('/api/polarion-matrix-testruns')
        .then(res => res.json())
        .then(data => {
          this.testruns = data.data
        })
    },
    submitTestrun (uuid) {
      this.$http.get(`/api/polarion-matrix-testruns/${uuid}/submit`)
    }
  },
  mounted () {
    this.refresh()
  }
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style>
</style>

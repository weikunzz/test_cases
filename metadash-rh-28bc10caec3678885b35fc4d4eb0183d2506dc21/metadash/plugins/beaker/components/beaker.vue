<template>
  <div>
    <ul class="nav nav-tabs">
      <router-link tag="li" active-class="active" to="/beaker/jobs">
        <a>My Group Running Jobs</a>
      </router-link>
      <router-link tag="li" active-class="active" to="/beaker/statistics">
        <a>Statistics</a>
      </router-link>
    </ul>
    <router-view></router-view>
  </div>
</template>

<script>
export default {
  name: 'beaker-navi',
  data () {
    return {}
  },
  mounted () {
  }
}
</script>

<!-- Add "scoped" attribute to limit CSS to this component only -->
<style scoped>
</style>

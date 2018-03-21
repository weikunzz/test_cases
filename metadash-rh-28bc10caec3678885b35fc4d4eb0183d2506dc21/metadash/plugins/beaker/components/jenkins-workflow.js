import Vue from 'vue'

class JenkinsBuild {
  constructor (data) {
    this.shouldTeardown = null
    this.triggerByRemote = null
    this.triggerByUpstream = null

    Object.assign(this, data)
    for (const action of data.actions) {
      if (action._class === 'hudson.model.ParametersAction') {
        for (const param of action.parameters) {
          if (param.name === 'TEARDOWN_SLAVE') {
            this.shouldTeardown = param.value
          }
        }
      }
      if (action._class === 'hudson.model.CauseAction') {
        for (const cause of action.causes) {
          if (cause._class === 'hudson.model.Cause$UpstreamCause') {
            this.triggerByUpstream = `${cause.upstreamBuild}`
          } else if (cause.addr && cause.addr === '10.73.73.55') {
            this.triggerByRemote = '10.73.73.55'
          }
        }
      }
    }
  }
  static async fetch (name, id = 'lastBuild') {
    return Vue.http.get(`https://libvirt-jenkins.rhev-ci-vms.eng.rdu2.redhat.com/job/${name}/${id}/api/json`)
      .then(res => res.json())
      .then(data => new JenkinsBuild(data))
      .catch(() => null)
  }
}

class JenkinsWorkflow {
  constructor (provisionFullName) {
    this.malformed = false
    this.status = null
    this.message = null
    try {
      this.provisionId = provisionFullName.match('.*?job/.+?/([0-9]+).*')[1]
      this.provisionName = provisionFullName.match('.*?job/(.+?)/.*')[1]
    } catch (e) {
      this.malformed = true
      return
    }
    this.runtestName = this.provisionName.replace('provision', 'runtest')
    this.teardownName = this.provisionName.replace('provision', 'teardown')
    this.provisionBuild = this.runtestBuild = this.teardownBuild = null
  }

  async fetchWorkflow () {
    if (this.malformed) {
      return
    }
    this.provisionBuild = await JenkinsBuild.fetch(this.provisionName, this.provisionId)
    if (!this.provisionBuild) {
      return
    }
    if (this.provisionBuild.result === 'FAILURE') {
      this.teardownBuild = await findByUpstream(this.provisionBuild, this.teardownName)
    } else {
      this.runtestBuild = await findByUpstream(this.provisionBuild, this.runtestName)
      if (this.runtestBuild) {
        this.teardownBuild = await findByUpstream(this.runtestBuild, this.teardownName)
      }
    }
  }
  genStatus () {
    if (this.malformed) {
      this.status = 'error'
      this.message = 'Malformed URL'
      return
    }

    if (!this.provisionBuild) {
      this.status = 'stall'
      this.message = 'Provision Not Found'
      return
    }

    if (!this.provisionBuild.result) {
      this.status = 'running'
      this.message = 'Provision In Progress'
      return
    }

    if (this.provisionBuild.result === 'FAILURE') {
      this.status = 'stall'
      this.message = 'Provision Failed'
      return
    }

    if (this.runtestBuild) {
      if (!this.runtestBuild.result) {
        this.status = 'running'
        this.message = 'Runtest In Progress'
        return
      }
    }

    if (!this.teardownBuild) {
      if (this.provisionBuild.shouldTeardown) {
        this.status = 'stall'
        this.message = 'Teardown Not Found'
      } else {
        this.status = 'waiting'
        this.message = 'Debug build'
      }
      return
    }

    if (!this.teardownBuild.result) {
      this.status = 'running'
      this.message = 'Teardown in progress'
      return
    }

    if (this.teardownBuild.result === 'FAILURE') {
      this.status = 'stall'
      this.message = 'Teardown Failed'
      return
    }
  }
}

async function findByUpstream (upstream, jobName, startID) {
  if (startID === 0) {
    return null
  }
  let build = await JenkinsBuild.fetch(jobName, startID)
  if (!build || build.timestamp < upstream.timestamp) {
    return null
  }
  if (build.triggerByUpstream === `${upstream.id}`) {
    return build
  }
  return await findByUpstream(upstream, jobName, build.id - 1)
}

export default JenkinsWorkflow

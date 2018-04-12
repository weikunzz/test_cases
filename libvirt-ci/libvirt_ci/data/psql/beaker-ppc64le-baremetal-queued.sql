SELECT
    u.user_name, COUNT(r.id) AS receipe_total
From
    Beaker.recipe AS r
    JOIN Beaker.recipe_set AS rs ON
        (r.recipe_set_id = rs.id)
    JOIN Beaker.job AS j ON
        (j.id = rs.job_id)
    JOIN Beaker.tg_user AS u ON
        (j.owner_id = u.user_id)
WHERE r.status LIKE 'Queued'
    AND "r._distro_requires" SIMILAR TO '%%ppc64le%%'
    AND "r._host_requires" !~ '.*hypervisor value="(VM|Xen|HyperV).*'
GROUP BY u.user_name
ORDER BY COUNT(r.id)
DESC LIMIT 10;


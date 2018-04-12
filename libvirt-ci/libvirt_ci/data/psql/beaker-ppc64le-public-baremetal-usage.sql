SELECT
    user_id, recipe_total, total_queued_minutes/60 AS total_queued_hours, total_used_minutes/60 AS total_used_hours, total_queued_minutes/recipe_total/60 AS queued_per_recipe, total_used_minutes/recipe_total/60 AS used_per_recipe
FROM
(
    SELECT
        u.user_name AS user_id, SUM(TIMESTAMPDIFF(sql_tsi_minute, rs.queue_time, r.start_time)) AS total_queued_minutes, SUM(TIMESTAMPDIFF(sql_tsi_minute, r.start_time, r.finish_time)) AS total_used_minutes, COUNT(r.id) AS recipe_total
    From
        Beaker.recipe AS r
        JOIN Beaker.recipe_set AS rs ON
            (r.recipe_set_id = rs.id)
        JOIN Beaker.job AS j ON
            (j.id = rs.job_id)
        JOIN Beaker.tg_user AS u ON
            (j.owner_id = u.user_id)
        JOIN Beaker.recipe_resource AS brr ON
            (r.id = brr.recipe_id)
    WHERE r.status LIKE 'Completed'
        AND "r._distro_requires" SIMILAR TO '%%ppc64le%%'
        AND r.start_time > '2016-02-15'
        AND "r._host_requires" !~ '.*hypervisor value="(VM|Xen|HyperV).*'
        AND brr.fqdn ~ '^ibm-p8-(firestone|garrison|habanero|rhevm).*'
    GROUP BY u.user_name
) SUBQ
ORDER BY total_used_hours
DESC;

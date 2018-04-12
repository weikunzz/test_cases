SELECT arch_t.arch AS arch_name, COUNT(bs.id) AS system_total
FROM Beaker.system AS bs
    JOIN Beaker.system_arch_map AS bsm ON
        (bs.id = bsm.system_id)
    JOIN Beaker.arch AS arch_t ON
        (arch_t.id = bsm.arch_id)
    JOIN Beaker.system_access_policy_rule AS bsapr ON
        (bs.custom_access_policy_id = bsapr.policy_id)
WHERE lab_controller_id IS NOT NULL
    AND bs.status = 'Automated'
    AND bs.loan_id is NULL
    AND bs.hypervisor_id IS NULL
    AND bs.type = 'Machine'
    AND bs.user_id IS NULL
    AND bsapr.group_id is NULL
    AND bsapr.permission = 'reserve'
GROUP BY arch_t.arch;

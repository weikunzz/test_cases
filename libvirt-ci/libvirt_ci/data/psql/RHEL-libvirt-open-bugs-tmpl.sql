SELECT b.bug_id, b.short_desc, b.version
FROM Bugzilla.bugs AS b
    JOIN Bugzilla.components AS c ON
        (b.component_id = c.id)
WHERE b.product_id = %s
    AND b.bug_status !~ '(ON_QA|CLOSED|VERIFIED)'
    AND b.component_id = %s
    AND b.rep_platform ~ '%s';

SELECT b.bug_id, b.short_desc, b.version
FROM Bugzilla.bugs AS b
    JOIN Bugzilla.components AS c ON
        (b.component_id = c.id)
WHERE b.product_id = %s
    AND b.bug_status = 'ON_QA'
    AND b.component_id = %s
    AND b.rep_platform ~ '%s';

SELECT blocked, string_agg(concat(dependson, ''), ',') AS total
FROM Bugzilla.dependencies
WHERE blocked = %s
GROUP BY blocked;

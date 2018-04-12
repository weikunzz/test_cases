SELECT id, level, uid FROM OC.oc_employee
WHERE id = 7211
UNION
SELECT id, level, uid FROM OC.oc_employee
WHERE manager_id = 7211 AND term_date is NULL;

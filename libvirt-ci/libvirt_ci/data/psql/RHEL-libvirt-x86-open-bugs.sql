SELECT b.bug_id, b.short_desc, b.cf_fixed_in, ft.name, p.login_name
FROM Bugzilla.profiles AS p
    JOIN Bugzilla.bugs AS b ON
        (p.userid = b.qa_contact)
    LEFT JOIN Bugzilla.flags AS f ON
        (b.bug_id = f.bug_id)
    JOIN Bugzilla.flagtypes AS ft ON
        (ft.id = f.type_id)
WHERE b.product_id in (151,201)
    AND b.bug_status = 'ON_QA'
    AND b.component_id in (73791,103761,94088,103926,134734,96683,104068)
    /*
    73791 - rhel6_libvirt
    103761 - rhel7_libvirt
    94088 - rhel6_netcf
    103926 - rhel7_netcf
    134734 - rhel7_libvirt-python
    96683 - rhel6_perl-Sys-virt
    104068 - rhel7_perl-Sys-virt
     */
    AND b.rep_platform ~ '(x86_64|Unspecified|All)'
    AND f.status='+'
    AND ft.name LIKE 'rhel%'
    AND NOT EXISTS(
        SELECT * FROM Bugzilla.keywords k
        LEFT JOIN Bugzilla.keyworddefs kd on
            k.keywordid=kd.id
        WHERE b.bug_id = k.bug_id and kd.name = 'OtherQA'
    );

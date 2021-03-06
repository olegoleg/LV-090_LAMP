"""Module implements common queries at ip addresses database, each represented
as a function (for now), each function takes MySQLdb.Connection as a first
parameter, other parameter depend on function itself. Functions use MySQLdb
library for executing queries and retrieving data"""
from datetime import datetime

import MySQLdb as mdb
from netaddr import IPAddress

from logger import create_logger

MODULE_LOGGER = create_logger('dbapi', 'dbapi.log')


def get_ip_data(ip_address):
    """Return value of ip address and ip version (value is integer if ip version
    is 4 and binary - if ip version is 6

    :param ip_address: ip address in string form.

    """
    ip = IPAddress(ip_address)
    ip_version = ip.version
    ip_value = ip.value if ip_version == 4 else bin(ip)
    return ip_value, ip_version


def get_ip_with_source_name(connection, sourcename, limit=None):
    """Get all ip addresses (if limit is not set), whose source name match
    to specified in function argument, if limit is set - output is limited to
    according values

    :param connection: MySQL database connection.
    :type connection: MySQLdb.connections.Connection.
    :param sourcename: The name of ip addresses source.
    :type sourcename: str.
    :param limit: A tuple of offset and row count.
    :type: limit: tuple.
    :returns: tuple -- each inner tuple contains all values from ip addresses
    table that match sourcename.

    """
    cursor = connection.cursor()
    sql = '''
    SELECT * FROM ip{0}_addresses
    WHERE id IN
    (
        SELECT source_to_addresses.{0}_id FROM source_to_addresses
        JOIN sources ON source_to_addresses.source_id = sources.id
        WHERE sources.source_name = "{1}"
    );'''
    if limit:
        # if "limit" parameter is set, add LIMIT clause to sql query
        sql = sql[:-1] + "LIMIT %s, %s;" % limit
    # create queries for v4 and v6 ip addresses
    sql_v4 = sql.format('v4', sourcename)
    sql_v6 = sql.format('v6', sourcename)
    # execute and fetch all results
    cursor.execute(sql_v4)
    result_v4 = cursor.fetchall()
    cursor.execute(sql_v6)
    result_v6 = cursor.fetchall()
    # close cursor and return all results
    result = result_v4 + result_v6
    cursor.close()
    MODULE_LOGGER.debug(
        'Searching for ips with source named "%s", found %s'
        % (sourcename, len(result))
    )
    return result


def get_ip_from_range(connection, start, end, limit=None):
    """Get all information about ip addresses in some range

    :param connection: MySQL database connection.
    :type connection: MySQLdb.connections.Connection.
    :param start: Start ip-address.
    :type start: str.
    :param end: End ip-address.
    :type end: str.
    :param limit: A tuple of offset and row count.
    :type: limit: tuple.
    :returns: tuple -- each inner tuple contains all values from ip addresses
    table within range.

    """
    cursor = connection.cursor()
    sql = '''
    SELECT * FROM ipv{0}_addresses
    WHERE address BETWEEN {1} AND {2};'''
    if limit:
        # if "limit" parameter is set, add LIMIT clause to sql query
        sql = sql[:-1] + " LIMIT %s, %s;" % limit
    # check if ip versions match
    start_value, start_version = get_ip_data(start)
    end_value, end_version = get_ip_data(end)
    if start_version != end_version:
        raise Exception("Different ip versions in start and end")
    # format query according to ip version, start and end values
    sql = sql.format(start_version, start_value, end_value)
    cursor.execute(sql)
    result = cursor.fetchall()
    cursor.close()
    MODULE_LOGGER.debug(
        'Searching for ips in range %s - %s, limit is %s, found %s'
        % (start, end, limit, len(result))
    )
    return result


def find_ip_list_type(connection, ip_address):
    """Find to which list ip address belongs

    :param connection: MySQL database connection.
    :type connection: MySQLdb.connections.Connection.
    :param ip_address: ip-address.
    :type start: str.
    :returns: str -- list name 'whitelsit' or 'blacklist' if found, else None

    """
    cursor = connection.cursor()
    sql = '''
    SELECT count(*) FROM {0}
    WHERE v{1}_id_{0} =
    (
        SELECT id FROM ipv{1}_addresses
        WHERE address = {2}
    );
    '''
    ip_value, ip_version = get_ip_data(ip_address)
    # format sql for whitelist and blacklist
    sql_whitelist = sql.format('whitelist', ip_version, ip_value)
    sql_blacklist = sql.format('blacklist', ip_version, ip_value)
    cursor.execute(sql_whitelist)
    # get number of address occurrences
    whitelist_count = cursor.fetchone()[0]
    cursor.execute(sql_blacklist)
    blacklist_count = cursor.fetchone()[0]
    if whitelist_count == blacklist_count:
        if whitelist_count > 0:
            raise Exception("Ip both in white and black lists, something wrong")
        return None
    cursor.close()
    list_name = 'whitelist' if whitelist_count > 0 else 'blacklist'
    MODULE_LOGGER.debug("Get %s list type. Found: %s" % (ip_address, list_name))
    return list_name


def get_ips_added_in_range(connection, startdate, enddate, limit=None):
    """Get information about ip addresses added since startdate till enddate

    :param connection: MySQL database connection.
    :type connection: MySQLdb.connections.Connection.
    :param startdate: Date range start.
    :type start: datetime.datetime.
    :param enddate: Date range end.
    :type enddate: datetime.datetime.
    :param limit: A tuple of offset and row count.
    :type: limit: tuple.
    :returns: tuple -- each inner tuple contains all values from ip addresses
    table within date range

    """
    if startdate > enddate:
        raise Exception("End date is before start date")
    sql = """
    SELECT * FROM ipv{0}_addresses
    WHERE date_added BETWEEN '{1}' AND '{2}';"""
    if limit:
        # if "limit" parameter is set, add LIMIT clause to sql query
        sql = sql[:-1] + " LIMIT %s, %s;" % limit
    # get formated date string
    cursor = connection.cursor()
    sql_v4 = sql.format(4, startdate.date(), enddate.date())
    cursor.execute(sql_v4)
    result_v4 = cursor.fetchall()
    sql_v6 = sql.format(6, startdate.date(), enddate.date())
    cursor.execute(sql_v6)
    result_v6 = cursor.fetchall()
    cursor.close()
    result = result_v4 + result_v6
    MODULE_LOGGER.debug(
        "Get ips added since %s till %s, limit is %s. Found: %s"
        % (startdate, enddate, limit, len(result))
    )
    return result_v4 + result_v6


def get_sources_modified_in_range(connection, startdate, enddate, limit=None):
    """Get information about sources modified since startdate till enddate

    :param connection: MySQL database connection.
    :type connection: MySQLdb.connections.Connection.
    :param startdate: Date range start.
    :type start: datetime.datetime.
    :param enddate: Date range end.
    :type enddate: datetime.datetime.
    :param limit: A tuple of offset and row count.
    :type: limit: tuple.
    :returns: tuple -- each inner tuple contains all values from ip addresses
    table within date range

    """
    cursor = connection.cursor()
    sql = '''
    SELECT * FROM sources
    WHERE url_date_modified
    BETWEEN "{0}" AND "{1}";'''.format(startdate.date(), enddate.date())
    if limit:
        # if "limit" parameter is set, add LIMIT clause to sql query
        sql = sql[:-1] + " LIMIT %s, %s;" % limit
    cursor.execute(sql)
    result = cursor.fetchall()
    cursor.close()
    MODULE_LOGGER.debug(
        "Get sources modified since %s till %s, limit is %s. Found: %s"
        % (startdate, enddate, limit, len(result))
    )
    return result


def check_if_ip_in_database(connection, ip_address):
    """Get information about sources modified since startdate till enddate

    :param connection: MySQL database connection.
    :type connection: MySQLdb.connections.Connection.
    :param ip_address: Ip address to check.
    :type ip_address: str.
    :returns: boolean -- True if ip in database, else False.

    """
    ip_value, ip_version = get_ip_data(ip_address)
    sql = '''
    SELECT count(id) FROM ipv{0}_addresses
    WHERE address = {1};
    '''.format(ip_version, ip_value)
    cursor = connection.cursor()
    cursor.execute(sql)
    result = cursor.fetchone()[0]
    cursor.close()
    result = True if result else False
    MODULE_LOGGER.debug(
        'Check if %s is in database. Returned: %s'
        % (ip_address, result)
    )
    return result

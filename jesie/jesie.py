# -*- coding: utf-8 -*-
import pyodbc


class Jesie(object):
    __connection_string = "DSN=test;DATABASE=PrestaOne;MARS_Connection=yes;UID=sa;PWD=SAPB1Admin"

    @staticmethod
    def __execute_query(query_string, params):
        cnxn = pyodbc.connect(Jesie.__connection_string, autocommit=True)
        cnxn.setdecoding(pyodbc.SQL_CHAR, encoding='cp850', to=str)
        cnxn.setencoding(str, encoding='cp850')
        cursor = cnxn.cursor()

        cursor.execute(query_string, params)

        cursor.close()
        cnxn.close()

    @staticmethod
    def write(oper_type, obj_type, obj_key, xml, xml_filtered=None):
        try:
            if xml_filtered:
                Jesie.__execute_query('EXEC OdooEnqueue ?, ?, ?, ?, ?', (oper_type, obj_type, obj_key, xml,
                                                                         xml_filtered))
            else:
                Jesie.__execute_query('EXEC OdooEnqueue ?, ?, ?, ?, NULL', (oper_type, obj_type, obj_key, xml))

            return True

        except Exception:
            raise

    @staticmethod
    def insert_jesie_prices(list_of_tuples, version, row_insert_limit=1000):
        # Tenemos que hacer inserciones en bloques de 1000 ya que es el máximo permitido.
        # The number of row value expressions in the INSERT statement exceeds the maximum allowed number of 1000 row
        # values.

        statement = "INSERT INTO [odoo_prices] ([type], [code], [item_code], [price], [version]) VALUES "
        values = ""

        counter = 0
        for t in list_of_tuples:
            if counter < row_insert_limit:
                values += "('{}', '{}', '{}', {}, '{}'),".format(t[0], t[1], t[2], t[3], version)
                counter += 1
            else:
                counter = 0
                values = values[:-1]
                Jesie.__execute_query(statement + values, ())
                values = ""

        if values:
            values = values[:-1]
            Jesie.__execute_query(statement + values, ())

    @staticmethod
    def delete_jesie_prices(version_to_preserve=None, version_to_delete=None):
        statement = "DELETE [odoo_prices]"

        if version_to_preserve:
            statement += " WHERE version <> '{}'".format(version_to_preserve)
        elif version_to_delete:
            statement += " WHERE version = '{}'".format(version_to_preserve)

        Jesie.__execute_query(statement, ())

    @staticmethod
    def jesie_enqueue_prices():
        Jesie.__execute_query('EXEC OdooEnqueuePrices', ())

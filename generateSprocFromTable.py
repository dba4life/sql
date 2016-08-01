# encoding: utf-8
'''
    Generate insert/update stored procedure from a SQL scripted create table 
    statement. 

    Removes spaces and hyphens from fields names for variable names.

'''
import sys
from math import floor

def parse(text):
    tableName = ''
    sprocName = ''
    fieldLine = 0
    
    # List of lists: 
    #    Field Name - Unaltered, square bracket delimited
    #    Variable Name - Prefixed '@i' (for input) removing spaces and hyphens
    #    Datatype
    #    Primary Key - Value of (1) indicates it is in primary key constraint
    #    Identity - Value of (1) indicates it is an identity column
    fields = []

    # Strip leading text; start with 'create table' line
    text = text[text.lower().find('create table'):]

    # Process script lines
    for line in text.split('\n'):
        line = line.strip()
        
        if(len(line) == 0):
            continue

        # Use 'create table' line and name to determine sproc name
        if(sprocName == ''):
            tableName = line[line.rfind('['):line.rfind(']')+1]

            sprocName = line[line.find('$')+1:line.find('])')-1]
            sprocName = sprocName.replace(' ', '') + 'Add'
            
            fieldLine = 1
            
        # Parse fields
        elif(fieldLine == 1 and line[0] == '['):
            fieldName = line[line.find('['):line.find(']')+1]

            variableName = fieldName[1:-1].replace(' ', '')
            variableName = '@i' + variableName.replace('-', '') 
                
            datatypeName = line[line.find(']')+3:]
            datatypeName = datatypeName[:datatypeName.find(' ')]
            datatypeName = datatypeName.replace(']', '')
            
            if(line.lower().find('identity(') >= 0):
                identityField = 1
            else:
                identityField = 0
            
            fields.append(([fieldName, variableName, datatypeName, 0, identityField]))
            
            if(line[-1] != ','):
                fieldLine = 0
        
        elif(fieldLine == 1 and line.lower().find('constraint')):
            fieldLine = 0

        # Fields in constraint clause
        elif(fieldLine == 0 and (line.find('ASC') or line.find('DESC'))):
            if(line.strip(' ')[0] == '['):
                fieldName = line[line.find('['):line.find(']')+1]

                # Find and update its list value
                for i in range(len(fields)):
                    if(fields[i][0] == fieldName):
                        fields[i][3] = 1
                        break

    # Generate create procedure statement
    build(tableName, sprocName, fields)

# Generate create procedure statement
def build(tableName, sprocName, fields):
    keyClause = ''

    # Check for primary key fields
    for pk in range(len(fields)):
        if(fields[pk][3] == 1):
            if(keyClause > ''):
                keyClause += '\t\t\tand '
            else:
                keyClause += '\t\t\t'
            
            keyClause += fields[pk][0] + ' = ' + fields[pk][1] + '\n'
    
    text = 'create procedure ' + sprocName + '(\n'
    
    for i in range(len(fields)):
        text += '\t' + fields[i][0] + pad(fields[i][0], 32) + fields[i][1] + '\n'
    
    # Check for primary key
    if(any(e[3] == 1 for e in fields)):
        text += ')\nas\nbegin\n'
        text += '\tdeclare @xReturn int\n\n'
        
        text += '\tif(exists(\n'
        text +=     '\t\tselect\n'
        text +=         '\t\t\t1\n'
        text += '\t\tfrom\n\t\t\t' + tableName + '\n' 
        text += '\t\twhere\n' 
    
        text += keyClause
                
        text += '\t))\n\tbegin\n'
        
        text += '\t\tupdate\n\t\t\t' + tableName + '\n\t\tset\n'
        
        for i in range(len(fields)):
            text += '\t\t\t' + fields[i][0] + pad(fields[i][0], 16) + ' = ' + fields[i][1] + '\n'

        text += '\tend\n\telse\n'
    
    # Build insert statement; excluding identity column if it exists
    text += '\tbegin\n'
    text += '\t\tinsert into ' + tableName + '(\n'
    
    # Insert fieldlist clause
    for i in range(len(fields)):
        if(fields[i][4] == 0):
            text += '\t\t\t' + fields[i][0]
            
            # Do not add a comma for the final field
            if(i < len(fields) - 1 and fields[i+1][4] != 1):
                text += ','
            
            text += '\n'
    text += '\t\t)\n\t\tvalues(\n'

    # Insert value clause
    for i in range(len(fields)):
        if(fields[i][4] == 0):
            text += '\t\t\t' + fields[i][1]
            
            # Do not add a comma for the final field
            if(i < len(fields) - 1 and fields[i+1][4] != 1):
                text += ','
            
            text += '\n'

    text += '\t\t)\n\tend\n'
    
    text += 'end\ngo\n'
    
    print(text)
    
def pad(baseString, width):
    return ' '*int(floor(((width - len(baseString)))))

# Takes a path, trolls each file and performs cleanup against them
def process(full_path):
    # Read file
    file = open(full_path, 'r').read()
    parse(file)
    
    return 1

def main(argv=None): # IGNORE:C0111
    sqlPath = 'C:\\dev\\wip.sql'
        
    process(sqlPath)
    
    exit(0)

if __name__ == "__main__":
    sys.exit(main())

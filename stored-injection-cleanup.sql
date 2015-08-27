/*
 * The following script identifies fields that have had a URL maliciously stored within varchar fields
 * and removes the injected string, leaving the original data. This cleanup effort was in response to
 * fields being maliciously updated to:
 *     [original data]<div><style="foo"><a href="evil.url"></div>
 * Cleanup assumes that the malicious div is at the end of the field. 
 * 
 * Script identifies all varchar/nvarchar columns with a length of at least 50 (##candiate)
 *
 * Removes fields that do not have all injection markers ['style', 'http', '<div', 'div>']
 *     (this preserves valid URLs in the database)
 *
 * Identifies unique injected strings (##injected)
 *
 * Cycles through candidate fields and removes, with replace function, the injected strings
 * 
 * Note that the output of candidateCursor, modified to include 'union all select' wrapped with 
 * select * from ([cursor]) as x where Total > 0 and (Style > 0 or Url > 0 or DivStart > 0 or DivEnd > 0)
 * can be used to determine the columns that are potentially exploited
 */
declare 
	@xSql	varchar(max)

create table ##candidate(
	TableName	varchar(100),
	Field		varchar(100),
	Style		int,
	Url			int,
	DivStart	int,
	DivEnd		int,
	Total		int
)

create table ##injected(
	string	varchar(1024)
)

declare candidateCursor cursor for
	-- Count injection markers for varchar fields
	select
		' ''' + c.TABLE_NAME + ''' TableName,
		''' + c.COLUMN_NAME + ''' Field,
		sum(case when [' + c.COLUMN_NAME + '] like ''%style=%'' then 1 else 0 end) Style,
		sum(case when [' + c.COLUMN_NAME + '] like ''%http%'' then 1 else 0 end) Url,
		sum(case when [' + c.COLUMN_NAME + '] like ''%<div%'' then 1 else 0 end) DivStart,
		sum(case when [' + c.COLUMN_NAME + '] like ''%div>'' then 1 else 0 end) DivEnd,
		count(1) Total
	 from 
		[' + c.TABLE_NAME + ']'
	from 
		INFORMATION_SCHEMA.COLUMNS c 
		inner join INFORMATION_SCHEMA.TABLES t 
			on t.TABLE_NAME = c.TABLE_NAME 
	where 
		t.TABLE_TYPE = 'BASE TABLE' 
		and c.DATA_TYPE like '%varchar' 
		and (
			c.CHARACTER_MAXIMUM_LENGTH >= 50 
			or c.CHARACTER_MAXIMUM_LENGTH = -1
		)
for read only

open candidateCursor

fetch next from candidateCursor into @xField

-- Do not display rowcounts for the candidate fields
set nocount on

while(@@fetch_status = 0)
begin
	exec('insert into ##candidate select' + @xSql)

	fetch next from candidateCursor into @xSql
end

close candidateCursor
deallocate candidateCursor

-- Injected columns contain 'http', 'style', '<div' and end with 'div>'
delete from 
	##candidate 
where 
	Total = 0	-- Empty table
	or Style = 0 
	or Url = 0 
	or DivStart = 0 
	or DivEnd = 0

set nocount off

-- Identify injected values
declare injectedCursor cursor for
	select
		'insert into 
			##injected
		select distinct
			substring(' + Field + ', 
				charindex(''<div'', ' + Field + '), 
				charindex(''</div>'', ' + Field + ') + 6 - charindex(''<div'', ' + Field + ')
			)
		from 
			' + TableName + ' 
		where 
			' + Field + ' like ''%div>''
			-- Exclude already inserted strings
			and substring(' + Field + ', 
				charindex(''<div'', ' + Field + '), 
				charindex(''</div>'', ' + Field + ') + 6 - charindex(''<div'', ' + Field + ')
			)
				not in(select string from ##injected)'
	from
		##candidate
for read only

open injectedCursor

fetch next from injectedCursor into @xSql

while(@@fetch_status = 0)
begin
	exec(@xSql)

	fetch next from injectedCursor into @xSql
end

close injectedCursor
deallocate injectedCursor

-- Cleanup
declare cleanupCursor cursor for
	select
		'update
			' + TableName + '
		set
			' + Field + ' = replace(' + Field + ', ''' + a.string + ''', '''')
		where
			' + Field + ' like ''%' + a.string + '%'''
	from
		-- why yes, I did intend that Cartesian Product...
		##candidate as i,
		##injected as a
for read only

open cleanupCursor

fetch next from cleanupCursor into @xSql

while(@@fetch_status = 0)
begin
	print @xSql
	exec(@xSql)

	fetch next from cleanupCursor into @xSql
end

close cleanupCursor
deallocate cleanupCursor

drop table ##candidate
drop table ##injected

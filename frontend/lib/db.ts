import * as duckdb from '@duckdb/duckdb-wasm'

let db: duckdb.AsyncDuckDB | null = null

async function getDB(): Promise<duckdb.AsyncDuckDB> {
  if (db) return db

  const JSDELIVR_BUNDLES = duckdb.getJsDelivrBundles()
  const bundle = await duckdb.selectBundle(JSDELIVR_BUNDLES)

  const worker_url = URL.createObjectURL(
    new Blob([`importScripts("${bundle.mainWorker!}");`], { type: 'text/javascript' })
  )
  const worker = new Worker(worker_url)
  const logger = new duckdb.ConsoleLogger()
  db = new duckdb.AsyncDuckDB(logger, worker)
  await db.instantiate(bundle.mainModule, bundle.pthreadWorker)

  return db
}

export async function query<T = Record<string, unknown>>(sql: string): Promise<T[]> {
  const database = await getDB()
  const conn = await database.connect()
  try {
    const result = await conn.query(sql)
    return result.toArray().map((row: any) => row.toJSON()) as T[]
  } finally {
    await conn.close()
  }
}

export async function queryGold<T = Record<string, unknown>>(sql: string): Promise<T[]> {
  return query<T>(sql.replace('{gold}', "read_parquet('../data/gold/gold.parquet')"))
}

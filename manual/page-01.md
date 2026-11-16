# 第 1 页 · 起一个会自己建库的 MySQL

## 这一页造什么

起一个叫 `lab-mysql` 的 MySQL 容器，端口只开给本机 `127.0.0.1:3307`；把 `fixtures/dw.sql` 挂进它的初始化目录，让容器第一次启动时自动建出 `dw` 库和 5 张表。

## 猜一猜

先写下答案，再动手。

`dw.sql` 你没有手动执行过。下面三条命令跑完，`SHOW TABLES` 会列出几张表？

- A. 0 张（脚本根本没执行）
- B. 5 张（脚本被自动执行了）
- C. 100 多张（连 MySQL 自带的系统表一起列出来）

## 动手

以下命令都在**仓库根目录**执行（有 `fixtures/`、`backend/` 的那一层）。

**第 1 条：起容器。**

```bash
docker run -d --name lab-mysql \
  -p 127.0.0.1:3307:3306 \
  -e LANG=C.UTF-8 \
  -e MYSQL_ROOT_PASSWORD=labpass \
  -e MYSQL_USER=didilili \
  -e MYSQL_PASSWORD=labpass \
  -v "$PWD/fixtures/dw.sql:/docker-entrypoint-initdb.d/10-dw.sql:ro" \
  "$(grep '^MYSQL_IMAGE=' .env.example | cut -d= -f2)"
```

它会打印一长串容器 ID，看到它就说明容器起来了。这一长串参数你只要记住这几处：

- `-p 127.0.0.1:3307:3306`：冒号左边是宿主机端口，右边是容器内端口。3306 常被本机已装的 MySQL 占着，所以这一课统一用 3307；3307 若也被占，换一个没被占的端口（比如 3308），后面写 3307 的页跟着改。
- `-v`：把 `fixtures/dw.sql` 只读（`:ro`）挂进容器的 `/docker-entrypoint-initdb.d/`。MySQL 官方镜像**第一次初始化时**会把这个目录里的 `.sql` 全跑一遍，所以你不必手动 `source`。
- `MYSQL_USER` / `MYSQL_PASSWORD`：`dw.sql` 里有 `GRANT ... TO 'didilili'@'%'`，而 MySQL 8 不会自动建这个用户，少了这两行容器会直接退出。
- `LANG=C.UTF-8`：让容器里的 `mysql` 认 UTF-8，少了它，下一页按中文筛数据会一条也筛不到。
- 最后一行不手抄镜像名，从仓库自带的 `.env.example` 里读 `MYSQL_IMAGE`（`.env` 是你本地的密钥配置，被 `.gitignore` 忽略，克隆下来没有）。这行一旦被改名或删除，命令会**静默传空**、拉不到镜像——所以别删它。

**第 2 条：等它初始化完。它一行输出都没有，是在等。**

```bash
until docker logs lab-mysql 2>&1 | grep -q 'port: 3306'; do sleep 2; done
```

正常 10–20 秒后光标才回来。超过 1 分钟还没回来，按 `Ctrl-C`，回看第 1 条有没有报错。

**第 3 条：看表。**

```bash
docker exec lab-mysql mysql -uroot -plabpass -N -B dw -e "SHOW TABLES;"
```

`dw` 是库名；`-N -B` 让输出只留表名，方便逐行对。终端里还会多一行 `mysql: [Warning] Using a password on the command line interface can be insecure.`——那是提醒你密码写在命令行上了，不是错误。

## 你应该看到

命令 3 的输出，5 行，顺序固定：

```text
dim_customer
dim_date
dim_product
dim_region
fact_order
```


![第 1 页 · 建库建表后 SHOW TABLES 的真实输出](images/page-01-mysql-tables.png)

## 对账

- 猜 A（0 张）：错。表是 `dw.sql` 建的，而它由 MySQL 在容器第一次初始化时自动执行——你没敲 `source`，不等于没执行。
- 猜 C（100 多张）：也不对。第 3 条末尾那个 `dw` 指定了库，只在 `dw` 里找表；MySQL 自带的系统表在 `mysql` 等库里，不会被列出来。
- 猜 B（5 张）：对。这 5 个名字就是 `dw.sql` 里的 5 个 `CREATE TABLE`，默认按字母顺序排。

自动执行只发生在容器**第一次**启动。重起同一个容器不会再跑 `dw.sql`；想从零再来，得 `docker rm -f lab-mysql` 删掉，再重跑第 1 条。

## 自己改一下

1. 去掉第 3 条里的 `-N` 再跑一次：第一行会多出表头 `Tables_in_dw`。
2. 把 `SHOW TABLES;` 换成 `SHOW DATABASES;`：除了 `dw`，还会列出 4 个 MySQL 自己的库。

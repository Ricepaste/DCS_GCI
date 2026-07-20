-- =========================================
-- DCS Map Data Exporter (Airbases & Coastline)
-- run via Mission Editor or Web Console
-- =========================================

local function export_map_data()
    env.info("=== DCS MAP DATA EXPORT START ===")
    
    -- 1. 匯出機場，並動態計算地圖掃描邊界
    -- 我們用所有機場的位置，向外擴張 200 公里作為海岸線掃描區域
    local min_x, max_x = 9999999, -9999999
    local min_z, max_z = 9999999, -9999999
    
    local airbase_count = 0
    for _, airbase in pairs(world.getAirbases()) do
        local p = airbase:getPoint()
        
        -- 取得跑道方向 (轉換為整數角度以避免浮點數逗號 Locale Bug)
        local course_deg = 0
        local runways = airbase:getRunways()
        if runways and #runways > 0 then
            course_deg = math.floor(math.deg(runways[1].course))
        end
        
        env.info(string.format("AIRBASE_PT:%s,%d,%d,%d", airbase:getName(), p.x, p.z, course_deg))
        
        if p.x < min_x then min_x = p.x end
        if p.x > max_x then max_x = p.x end
        if p.z < min_z then min_z = p.z end
        if p.z > max_z then max_z = p.z end
        
        airbase_count = airbase_count + 1
    end
    
    -- 防禦性設計：若地圖沒有機場，給定預設區域
    if airbase_count == 0 then
        min_x, max_x, min_z, max_z = -500000, 500000, -500000, 500000
    end
    
    -- 向外擴充 200 公里 (200,000 公尺) 以涵蓋外海與偏遠海岸
    local padding = 200000
    min_x = min_x - padding
    max_x = max_x + padding
    min_z = min_z - padding
    max_z = max_z + padding
    
    -- 輔助函式：判斷是否為外海 (過濾內陸河道與湖泊)
    local function is_water(x, z)
        local t = land.getSurfaceType({x=x, y=z})
        return t == land.SurfaceType.WATER or t == land.SurfaceType.SHALLOW_WATER
    end
    local function ray_is_water(x, z, dx, dz, max_d)
        for d = 2000, max_d, 2000 do
            if not is_water(x + dx*d, z + dz*d) then return false end
        end
        return true
    end
    local function is_open_ocean(x, z)
        if land.getHeight({x=x, y=z}) >= 2 then return false end
        if not is_water(x, z) then return false end
        
        -- 真實海洋探測：必須在東南西北任一方向，擁有連續 8 公里的水體，絕對不能跨越陸地
        local max_d = 8000
        if ray_is_water(x, z, 1, 0, max_d) then return true end
        if ray_is_water(x, z, -1, 0, max_d) then return true end
        if ray_is_water(x, z, 0, 1, max_d) then return true end
        if ray_is_water(x, z, 0, -1, max_d) then return true end
        return false
    end

    -- 2. 掃描海岸線 (動態適應任意地圖如敘利亞、馬里亞納等)
    local step = 2000 -- 2公里的高解析度
    local coast_count = 0
    local coast_buffer = "COASTLINE_PT:"
    local coast_buf_count = 0
    
    for x = max_x, min_x, -step do
        for z = min_z, max_z, step do
            if is_open_ocean(x, z) then
                if not is_water(x+step, z) or not is_water(x-step, z) or not is_water(x, z+step) or not is_water(x, z-step) then
                    coast_buffer = coast_buffer .. string.format("%d,%d;", x, z)
                    coast_buf_count = coast_buf_count + 1
                    coast_count = coast_count + 1
                    
                    if coast_buf_count >= 200 then
                        env.info(coast_buffer)
                        coast_buffer = "COASTLINE_PT:"
                        coast_buf_count = 0
                    end
                end
            end
        end
    end
    if coast_buf_count > 0 then env.info(coast_buffer) end
    
    -- 3. 掃描海洋填色區域 (降低解析度以節省效能)
    local sea_step = 8000
    local sea_count = 0
    local sea_buffer = "SEA_PT:"
    local sea_buf_count = 0
    
    for x = max_x, min_x, -sea_step do
        for z = min_z, max_z, sea_step do
            if is_open_ocean(x, z) then
                sea_buffer = sea_buffer .. string.format("%d,%d;", x, z)
                sea_buf_count = sea_buf_count + 1
                sea_count = sea_count + 1
                
                if sea_buf_count >= 200 then
                    env.info(sea_buffer)
                    sea_buffer = "SEA_PT:"
                    sea_buf_count = 0
                end
            end
        end
    end
    if sea_buf_count > 0 then env.info(sea_buffer) end
    
    env.info(string.format("=== DCS MAP DATA EXPORT END | Airbases: %d, Coastline: %d, Sea: %d ===", airbase_count, coast_count, sea_count))
end

export_map_data()
